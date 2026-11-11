# Nebula Strike — CG 開場動畫

用程式產生的 16 秒 CG 過場動畫（1280×720、30fps、2.39:1 電影黑邊）。

| 時間 | 鏡頭 |
|---|---|
| 0–4s | 戰機從紫藍色星雲中衝出，貼近鏡頭飛掠 |
| 4–9s | 追尾鏡頭，與 7 架敵機交火，逐一擊落 |
| 9–12s | 低角度側拍，蓄力砲擊中母艦，連鎖爆炸、白光 |
| 12–16s | 爆炸餘燼中浮現標題 **NEBULA STRIKE** |

## 怎麼產生

需要 Node.js、Playwright（Chromium）、ffmpeg、Python 3 + numpy。

```bash
./build.sh            # 輸出 out/nebula_strike_cinematic.mp4
node render.js --stills 3.9,6.7,10.4,14   # 只輸出幾張預覽圖
```

- `scene.html` — Three.js 場景：程式建模的戰機／敵機／母艦、星雲、行星、雷射、粒子爆炸、Bloom 光暈與調色。所有動畫都是時間 `t` 的函數，可逐格重現。
- `render.js` — 用無頭 Chromium 一格一格渲染，PNG 直接丟給 ffmpeg 編碼。
- `audio.py` — 依 `out/events.json`（雷射、爆炸時間點）用 numpy 合成配樂與音效。
