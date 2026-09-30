# Carnival TKL 固件反编译分析 & GIF 屏幕开关键 / 自动休眠补丁

对象：`Carnival_TKL_v5.uf2`（Matrix Lab Carnival TKL，v5 固件）

## 1. 固件概况

| 项目 | 结果 |
| --- | --- |
| 格式 | UF2，family `0x57755A57`（STM32F4），503 块 × 256 B |
| 加载地址 | `0x08020000`（前 128 KB 是 UF2 bootloader） |
| MCU | STM32F411（初始 SP = `0x20020000`，128 KB RAM） |
| 固件框架 | **AMK**（[yulei/amk](https://github.com/yulei/amk)，TMK 按键核心 + TinyUSB + STM32 HAL），带 Vial（`vial:f64c2b3c`） |
| 屏幕 | 128×128 RGB565 SPI LCD（ST7735/GC9107 类，列/行偏移 +2/+3），帧缓冲 32 KB @ `0x20000816` |
| 屏幕电源 | **PB9**，低电平上电（`power_on = 0`） |
| GIF 存储 | W25Q128 SPI Flash + FatFs，USB MSC 模式下可当 U 盘拷贝 `.anm` 动画 |
| 其他 Flash 分区 | `0x08010000` EEPROM 模拟；`0x08040000–0x0805FFFF` OTA 暂存区 |

公开的 yulei/amk 仓库里没有 Carnival TKL 的键盘目录，而且这个固件的屏幕代码比仓库里通用的
`render.c / display.c` 精简得多（像是键盘专用实现），所以下面的内容是直接从反汇编还原的。

## 2. 屏幕相关代码还原（伪 C）

```c
// ---- RAM ----
struct anim_screen {            // @ 0x20000210
    uint8_t  anim_index;        // +0x00
    uint32_t x, y, w, h;        // +0x04..+0x10  (0,0,128,128)
    uint32_t delay;             // +0x14
    uint32_t mode;              // +0x18  单个/顺序/随机，F16 或 0x7E07 键循环切换
    anim_t  *anim;              // +0x1C
    uint8_t *buffer;            // +0x20  = 0x20000816
    uint32_t buffer_size;       // +0x24  = 0x8000
    uint32_t ticks;             // +0x28
} S;
uint8_t screen_on = 1;          // @ 0x20000240  只在运行时使用，不存 EEPROM
screen_driver_param_t drv_param;// @ 0x20000244  {ctrl=NC, power=PB9, power_on=0, ...}
uint8_t reload_anim;            // @ 0x20008816  由 AMK 协议 "start display" 置 1

// 0x080225E4 —— 真正的屏幕上/下电函数
static void screen_power(bool on) {
    if (on) {
        gpio_write_pin(PB9, 0);             // 给屏幕上电
        wait_ms(1);
        lcd_init(&lcd, &drv_param);         // 0x08022A5C，发初始化序列
        lcd_display_on(&lcd);               // 0x080229C4
    } else {
        memset(S.buffer, 0, S.buffer_size);
        lcd_fill(&lcd, 0, 0, 128, S.buffer, S.buffer_size);  // 先刷黑
        gpio_write_pin(PB9, 1);             // 再断电
        wait_ms(1);
    }
}

// 0x080227F4
void screen_set_power(bool on) {
    if (screen_on != on) { screen_on = on; screen_power(on); }
}

// 0x08022700  (amk_init 末尾经 0x080222F2 调用)
bool screen_init(void) { /* 配 SPI 引脚、screen_power(screen_on)、挂载 FatFs、打开第一个动画 */ }

// 0x0802279C  (主循环每轮经 0x080222F6 调用)
void screen_task(void) {
    if (usb_setting & USB_MSC_BIT) return;  // U 盘模式不播
    if (!screen_on) return;                 // 屏幕关着就不播
    if (reload_anim) { reopen_anim(); reload_anim = 0; }
    anim_display_task(&S);                  // 0x08022660：按帧延时读 Flash、刷屏
}

// 0x08027DEC / 0x08027E08 —— USB 挂起 / 唤醒
void suspend_power_down(void) { if (!suspended) { rgb_off();  screen_set_power(0); suspended = 1; } }
void suspend_wakeup_init(void){ if (suspended)  { rgb_on();   screen_set_power(1); suspended = 0; } }
```

结论：

* 固件里**已经有完整的"关屏"逻辑**（刷黑 + PB9 断电），但只在**电脑休眠/USB 挂起**时调用。
* 没有任何"空闲 N 分钟后关屏"的计时逻辑，这就是要加的部分。
* AMK 协议里的 `stop display` 命令处理函数（`0x08022818`）是空函数，改键软件那边的"停止显示"其实什么也不做。
* 固件里的 Vial 定义（xz 压缩 JSON，`0x0803C6CC`，1924 字节）有 9 个自定义键，对应键码 `0x7E00 + 序号`：

  | 键码 | 名称 | 作用 |
  | --- | --- | --- |
  | 0x7E00–0x7E03 | FS1K / HS2K / HS4K / HS8K | 回报率 |
  | 0x7E04–0x7E06 | RGB_NXT / RGB_GLB / RGB_TST | RGB |
  | 0x7E07 | SCR_MOD | 切换屏幕播放模式（`KC_F16` 也会触发） |
  | 0x7E08 | SCR_DSK | 进入/退出屏幕 U 盘模式并重启（`KC_F24` 也会触发） |

  **没有开关屏幕的键**。

## 3. 怎么加开关键 / 自动休眠

开关键：新增自定义键码 `SCR_TOG = 0x7E09`，在 `process_record_kb` 里按下时调用
`screen_set_power(!screen_on)`，并记一个"手动关闭"标志，免得被电脑唤醒或自动休眠逻辑又打开。

自动休眠的思路：

1. 每次有按键事件就记下当前时间 `last_activity = timer_read32()`；
2. 主循环里检查 `timer_elapsed32(last_activity) > TIMEOUT`，超时就 `screen_set_power(0)`；
3. 有新按键、屏幕又是关着的，就 `screen_set_power(1)`。

### 方案 A：有源码（自己用 AMK 编译）

在键盘目录的 `.c` 里加（函数名换成你源码里对应的）：

```c
#define SCREEN_IDLE_TIMEOUT (5 * 60 * 1000)   // 5 分钟
static uint32_t last_activity;

bool process_record_kb(uint16_t keycode, keyrecord_t *record) {
    last_activity = timer_read32();
    /* ...原来的逻辑... */
}

void suspend_wakeup_init_kb(void) {
    last_activity = timer_read32();
    screen_set_power(true);
}

void render_task(void) {           // 或者自己的 custom_task
    if (!(usb_setting & USB_MSC_BIT) && !suspended) {
        bool idle = timer_elapsed32(last_activity) > SCREEN_IDLE_TIMEOUT;
        if (idle && screen_on)       screen_set_power(false);
        else if (!idle && !screen_on) screen_set_power(true);
    }
    /* ...原来的动画刷新... */
}
```

如果用的是 yulei/amk 仓库里通用的 `render.c`，也可以调 `render_enable_display(i, false)`，
不过它只是停止刷新，屏幕本身不断电；要真正省电，得像上面这样拉高电源脚（`SCREEN_0_PWR`）。

开关键（源码版）：

```c
enum { SCR_TOG = 0x7E09 };        // 并在 vial.json 的 customKeycodes 末尾加一项
static bool manual_off;

bool process_record_kb(uint16_t keycode, keyrecord_t *record) {
    if (keycode == SCR_TOG) {
        if (record->event.pressed) {
            manual_off = screen_on;
            screen_set_power(!screen_on);
        }
        return false;
    }
    /* ... */
}
// suspend_wakeup_init_kb / render_task 里 manual_off 为真时不要去开屏
```

### 方案 B：没有源码，直接给二进制打补丁（本目录）

Carnival TKL 的源码没有公开，所以我把上面的逻辑写成 232 字节的 Thumb-2 汇编（`screen_patch.S`），
放进固件镜像末尾没用到的全 0 填充区（`0x0803E000`），然后改 5 条跳转：

| 地址 | 原指令 | 改为 | 作用 |
| --- | --- | --- | --- |
| `0x080222F2` | `b.w screen_init` | `b.w init_hook` | 开机时初始化计时 |
| `0x080222F6` | `b.w screen_task` | `b.w task_hook` | 每轮检查是否超时，决定关/开屏 |
| `0x0802A670` | `bl process_record` | `bl record_hook` | 任何按键按下/松开都算活动 |
| `0x08027E14` | `bl suspend_wakeup_kb` | `bl resume_hook` | 电脑唤醒也算活动；手动关屏时唤醒后保持关闭 |
| `0x0802AA98` | `bl process_record_kb` | `bl kb_hook` | 处理 `SCR_TOG`（0x7E09），其他键原样交给原函数 |

用到的两个 RAM 变量都放在原固件没用到的空隙里：

* 计时 `0x2000058C`：`.data` 结尾和 `.bss` 开头之间的 4 字节对齐空隙；
* 手动关闭标志 `0x20000241`：`screen_on` 字节后面的填充字节，启动时被 `.data` 初始化为 0。

另外把 Vial 定义解压，在 `customKeycodes` 末尾加上 `SCR_TOG`，重新 xz 压缩后放到 `0x0803E200`，
并改掉 Vial 协议里读定义用的指针（`0x0802CF04`）和 3 处长度常量（`0x0802CD42/46/56/68`）。
这样 Vial 的 "User" 页里就会多出一个 **Screen On/Off** 键。

生成补丁固件：

```bash
sudo apt install binutils-arm-none-eabi      # 需要 arm-none-eabi-as/ld/objcopy/nm
python3 patch_fw.py Carnival_TKL_v5.uf2 -o Carnival_TKL_v5_screen.uf2          # 只加开关键
python3 patch_fw.py Carnival_TKL_v5.uf2 -t 300 -o Carnival_TKL_v5_screen.uf2   # 开关键 + 空闲 300 秒自动休眠
```

脚本会先校验原固件的 SHA-256 和 4 个补丁点的原始字节，不是同一个 v5 固件就直接拒绝，
不会生成坏固件。

效果：

* 在 Vial 里把某个键（比如 Fn 层的某个键）设成 User 页的 **Screen On/Off**；
* 按一下 → 屏幕刷黑并断电（PB9），GIF 停止；再按一下 → 重新上电继续播放；
* 手动关掉后，普通按键和电脑唤醒都**不会**把它打开，只有再按开关键才开；
  这个状态不保存，重新插拔键盘后屏幕默认是亮的；
* 如果加了 `-t N`：连续 N 秒没按键自动关屏，按任意键自动亮屏（这次按键照常输入）；
  自动休眠时按开关键也会直接亮屏；
* 电脑休眠/唤醒、U 盘（MSC）模式的原有行为不变。

如果 Vial 里没看到新键，也可以在 "Any" 键里直接填 `0x7E09`。

刷机：和平时一样进入 UF2 bootloader，把新的 `.uf2` 拖进 U 盘。bootloader 在 `0x08000000`，
不会被覆盖，出问题随时刷回原版 `Carnival_TKL_v5.uf2`。

> ⚠️ 这个补丁在反汇编层面逐条核对过（跳转编码、调用约定、栈对齐、补丁区为空），
> 但我手上没有实物键盘，没有上机测试。
