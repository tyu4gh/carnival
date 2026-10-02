基于 Matrix Lab **Carnival TKL v5** 原厂固件（AMK / STM32F411）的二进制补丁版：
加了屏幕开关键，以及屏幕 + 灯光一起自动休眠。已在实机刷入测试。

## v1.1 更新
- 修复：自动休眠后按键唤醒时打字会卡顿、并连续输出唤醒时那个字符的问题。
  原因是旧版唤醒要重新初始化屏幕（约 0.7 秒的阻塞延时），期间键盘停止扫描，
  松键事件被推迟，系统便把该键当成长按一直重复。新版唤醒不再重新初始化屏幕，
  瞬间恢复，打字不受影响。

## 新功能

### 🖥️ 屏幕开关键 `Screen On/Off`（SCR_TOG，`0x7E09`）
- 按一下关屏：先刷黑，再切断屏幕供电（PB9），GIF 停止播放；再按一下重新上电继续播放。
- 手动关屏后，普通按键、自动休眠逻辑、电脑唤醒都**不会**把它打开，只有再按开关键才亮。
- 状态不保存：重新插拔键盘后屏幕默认是亮的。

### 💤 屏幕 + 灯光自动休眠（空闲 5 分钟）
- 连续 5 分钟没有按键 → 屏幕变黑停播，**全部 62 颗 RGB 灯珠熄灭**
  （两侧灯圈、5×5 灯阵、右侧灯条、指示灯、徽标）。
- 按任意键 → 屏幕和灯光立刻恢复，灯效接着原来的设置继续；这次按键照常输入，不会被吞，也不会卡顿。
- 自动休眠**不再切断屏幕供电**（只是停播并刷黑），所以唤醒时不需要重新初始化屏幕，
  主循环不会被阻塞，打字不会卡顿或连续输出同一个字符。
- 灯光只看空闲时间，和开关键无关：手动关了屏幕，灯光照常亮，空闲后照样熄灭。
- 灯光休眠用的是原厂 USB 挂起时关灯的同一个运行时标志，**不写入灯光设置**，调好的灯效不会丢。
- 电脑休眠/唤醒、屏幕 U 盘模式的原厂行为不变。

### 🎞️ GIF 切换键 `GIF Next` / `GIF Prev`（SCR_NXT `0x7E0A` / SCR_PRV `0x7E0B`）
- 跳到下一个 / 上一个 GIF，首尾循环，打不开的文件自动跳过。
- 开机播放方式保持原厂默认（按顺序轮播），`Screen Mode`（SCR_MOD）照旧切换单个循环 / 顺序播放。

新键都已写进固件内置的 Vial 定义，在 vial.rocks / Vial 的 **User** 页可以直接拖到键位上
（找不到的话在 **Any** 页输入键码）。

## 刷机方法

1. 下载下面的 `Carnival_TKL_v5_screen_toggle_sleep300s_rgb.uf2`。
2. 拔掉键盘，**按住 Esc** 再插上电脑，电脑上会出现一个 U 盘。
3. 把 `.uf2` 拖进这个 U 盘，写完键盘会自动重启（系统提示"磁盘未正常推出"属正常现象）。
4. 打开 [vial.rocks](https://vial.rocks)（Chrome / Edge），在 User 页把 **Screen On/Off** 等新键放到键位上。

**恢复原版**：同样按住 Esc 插线，把原厂 `Carnival_TKL_v5.uf2` 拖进去即可。
按住 Esc 的检测比补丁代码更早执行，bootloader 也不会被覆盖，所以随时可以刷回。

## 注意
- ⚠️ 只适用于 **Carnival TKL v5** 原厂固件，别刷到其他键盘或其他版本。
- 原厂固件里 **F16 = 切换屏幕播放模式，F24 = 进入 U 盘模式并重启**，键位里慎用这两个键。
- 想要别的休眠时间，或者只休眠屏幕、灯光常亮，可以用仓库里的 `screen_sleep/patch_fw.py`
  自己生成（需要原厂 v5 固件）：
  ```
  python3 screen_sleep/patch_fw.py Carnival_TKL_v5.uf2 -t 600 --sequence -o out.uf2              # 10 分钟
  python3 screen_sleep/patch_fw.py Carnival_TKL_v5.uf2 -t 300 --sequence --no-rgb-sleep -o out.uf2  # 灯光不休眠
  ```
- 反编译分析和实现细节见 [`screen_sleep/README.md`](https://github.com/tyu4gh/carnival/blob/claude/keyboard-firmware-screen-sleep-5rld7z/screen_sleep/README.md)。
- 这是非官方修改版，与 Matrix Lab 无关，刷机风险自负。

## 校验
```
SHA-256  e4a5860966d1dfa828f70e736cc9544b096dab06a1a81e26df729e0b4d94a73e  Carnival_TKL_v5_screen_toggle_sleep300s_rgb.uf2
```
