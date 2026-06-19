# Coze 机器人配置指南

## 第一步：创建 Bot

1. 打开 [Coze 官网](https://www.coze.cn) 并登录
2. 点击左侧「创建 Bot」按钮
3. Bot 名称填写：**数学教学助手**
4. Bot 功能介绍：**用于学生数学作业批改、智能出题、生成诊断报告和学习计划**
5. 点击「确认」

## 第二步：配置 Bot 人设与回复逻辑

在 Bot 编辑页面的「人设与回复逻辑」中输入以下内容：

```
你是一个耐心、鼓励式数学老师，擅长用通俗易懂的语言讲解数学概念。
你需要用 JSON 格式回复，以便系统解析。

请严格按照用户要求的 JSON 格式返回数据，不要添加额外的解释文本。
```

## 第三步：设置 Prompt 模板（关键）

在 Bot 的「知识」或「开场白」中，不需要填写固定内容。Prompt 由我们的后端程序自动发送。

你只需要在 Bot 的「功能设置」→「模型设置」中选择合适的模型（建议选择**Claude** 或 **GPT-4o**，效果最好），其他设置保持默认即可。

## 第四步：发布 Bot

1. 点击右上角的「发布」按钮
2. 选择发布渠道「API」，因为我们要通过后端调用
3. 点击「确认发布」

## 第五步：获取 Bot ID

1. 发布后回到 Bot 编辑页面
2. 查看浏览器地址栏，URL 格式如下：
   ```
   https://www.coze.cn/space/xxxxxx/bot/yyyyyy
   ```
   其中 `yyyyyy` 就是你的 **Bot ID**

## 第六步：获取 Personal Access Token

1. 点击 Coze 页面右上角的**头像** → 「设置」
2. 找到 **「API 令牌」** 或 **「Personal Access Token」** 选项
3. 点击「创建新令牌」
4. 填写令牌名称（如 `math-teaching`）
5. 选择权限范围，勾选「chat」和「bot」相关权限即可
6. 点击「确认」→ **复制生成的 Token 并保存好**（关闭页面后不再显示）

## 第七步：配置到项目

在 `math-teaching-agent/backend/` 目录下创建 `.env` 文件：

```env
COZE_BOT_ID=这里填你的BotID
COZE_TOKEN=这里填你的PersonalAccessToken
```

## 验证是否配置成功

启动后端后访问：
```
curl http://localhost:8000/api/health
```

返回 `{"status":"ok"}` 即表示运行正常。

> **注意**：Coze API 调用需要科学上网环境，否则可能无法连接。
> 如果不配置 Coze，前端页面可以正常浏览，但批改和出题功能会报错。
