# Ember 前端

Ember 的 Next.js 16 前端（App Router + React 19 + Tailwind CSS 4）。

## 开发

```bash
npm install
npm run dev
```

打开 [http://localhost:3000](http://localhost:3000)。

## 构建与部署

```bash
npm run build
npm run start
```

Docker 构建使用 `output: 'standalone'`，镜像见仓库根目录 `Dockerfile`。

## 设计系统

整体风格为 **Ember（炉火余烬）**：

- 设计令牌（颜色、圆角、阴影、渐变）集中在 `src/app/globals.css`
- 默认暖暗色：炉渣炭黑 + 蜜色文字 + 余烬橘；亮色伴生模式为暖象牙白
- 热度条使用“余烬→琥珀”渐变作为签名元素
- 组件类：`.card`、`.btn-primary`、`.chip`、`.input`、`.kicker` 等，可直接复用
