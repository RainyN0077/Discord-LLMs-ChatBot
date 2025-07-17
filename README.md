<div align="center">
  <h1>Discord LLM Chatbot 🤖</h1>
  <p>
    A highly customizable, multi-provider LLM chatbot for Discord with a powerful web UI and a secure, RESTful plugin system.
    <br />
    一个高度可定制、支持多服务商、带Web界面和安全RESTful插件系统的Discord大语言模型机器人。
  </p>
  <table>
    <tr>
      <td align="center">
        <b>强大的Web控制面板</b><br>
        <img src="https://cdn.discordapp.com/attachments/1341259395396272180/1395303769310363709/Opera__2025-07-17_151639_127.0.0.1.png?ex=6879f566&is=6878a3e6&hm=a320ffe6a9b7dff856ebe93b431de1c02b9a2ea4f584832fc986d0585917dc2f&" alt="Web UI Overview" width="440">
      </td>
      
    </tr>
  </table>
</div>
 
---
 
<details>
<summary><strong>English Readme (Click to expand)</strong></summary>

## ✨ Features

- **✅ Multi-Provider Support**: Seamlessly switch between **OpenAI** (and compatible APIs), **Google Gemini**, and **Anthropic Claude**.
- **✅ Powerful Web UI**: A comprehensive control panel to configure every aspect of the bot in real-time without touching code.
- **✅ Secure RESTful Plugin System**:
    -   Create custom tools that call external APIs, triggered by commands or keywords in Discord.
    -   Exposes a secure endpoint (`/api/plugins/trigger`) protected by an auto-generated API Key.
    -   Allows external services (like IFTTT, Zapier, or custom scripts) to securely trigger your plugins.
    -   Supports two action types: direct HTTP output or LLM-augmented summaries for smarter responses.
- **✅ Role-Based Configuration**: Assign unique personalities, custom titles, and usage quotas (message/token limits) to different Discord roles.
- **✅ Quota Management**: Built-in usage tracking for roles. Users can check their remaining quota with a simple `!myquota` command.
- **✅ Advanced Context Awareness**: The bot reads chat history (configurable limits) to understand conversations deeply.
- **✅ Layered Persona System**: The bot's personality is determined by a clear priority: `User-specific Persona > Role-based Persona > Default Persona`.
- **✅ Dockerized & Easy Setup**: Get up and running in minutes with a single `docker-compose` command.
- **✅ Multilingual UI**: Switch between English and Chinese on the fly.

## 🛠️ Setup & Installation

### Prerequisites

- [Docker](https://www.docker.com/get-started)
- [Docker Compose](https://docs.docker.com/compose/install/)

### Installation

1.  **Clone the repository:**
    ```sh
    git clone https://github.com/RainyN0077/Discord-LLMs-ChatBot.git
    cd Discord-LLMs-ChatBot
    ```

2.  **Build and run the containers:**
    ```sh
    docker-compose up --build -d
    ```

3.  **Configure the bot:**
    - Open your web browser and navigate to `http://localhost:8080`.
    - Fill in all the required configurations, especially your **Discord Bot Token** and **LLM API Key**.
    - Your unique **RESTful API Key** will be automatically generated and displayed in the "Global Configuration" section.
    - Explore the different configuration cards to customize the bot to your liking.
    - Click **"Save Configuration & Restart Bot"**.

4.  **You're all set!** Invite your bot to your Discord server and start chatting! Use `!myquota` to check your limits or trigger a plugin you've configured.

## 🔧 Configuration Guide

All configurations are managed through the web UI at `http://localhost:8080`.

-   **Global & LLM Provider**: The basics. Set your Discord Bot Token, choose your LLM provider, and enter the corresponding API Key.
-   **Context Control**: Define how many past messages the bot should read for context. Use `Channel Mode` for public discussions or `Memory Mode` for a personal assistant style.
-   **User Portraits**: Assign a custom nickname and a unique personality to a specific user ID. This has the highest priority.
-   **Role-Based Configuration**:
    -   Assign a custom title and personality to users with a specific Discord Role ID.
    -   Set message or token limits (e.g., 100 messages per hour, 50,000 tokens per day).
    -   Customize the color of the quota embed.
-   **Plugin Manager**:
    -   Click "Add Plugin" to create a new tool.
    -   **Name** it, **Enable** it, and set a **Trigger Type** (`Command` like `!weather` or `Keyword` like `search for`).
    -   Set up the **HTTP Request** (URL, method, headers). You can use placeholders like `{user_input}`.
    -   Choose an **Action Type**:
        -   `HTTP Request (Direct Output)`: The bot will post the raw API response.
        -   `LLM-Augmented Tool`: The bot will feed the API response to the LLM with your custom prompt template (using `{api_result}`) to generate a natural language summary.

## 🔌 Using the RESTful API

This bot exposes a secure RESTful endpoint to trigger plugins externally.

-   **Endpoint**: `POST /api/plugins/trigger`
-   **Authentication**: You must include your unique API Key in the `X-API-Key` header of your request. You can find and copy your key in the "Global Configuration" section of the web UI.
-   **Request Body**:
    ```json
    {
      "plugin_name": "Your Plugin Name",
      "args": {
        "any_key": "any_value",
        "another_key": 123
      }
    }
    ```
    The `args` object will be converted to a JSON string and used to replace the `{user_input}` placeholder in your plugin's URL and body templates.

**Example using cURL:**
```sh
curl -X POST http://localhost:8080/api/plugins/trigger \
-H "Content-Type: application/json" \
-H "X-API-Key: YOUR_GENERATED_API_KEY_FROM_UI" \
-d '{
  "plugin_name": "Weather Check",
  "args": {
    "city": "London"
  }
}'
```

## 📄 License

This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for details.

</details>

<br>

<details open>
<summary><strong>中文说明 (点击展开)</strong></summary>

## ✨ 功能特性

- **✅ 多服务商支持**: 可在 **OpenAI** (及兼容API)、**Google Gemini**、**Anthropic Claude** 之间无缝切换。
- **✅ 强大的Web控制面板**: 一个全面的网页控制台，无需接触代码即可实时配置机器人的方方面面。
- **✅ 安全的RESTful插件系统**:
    -   创建自定义工具，通过Discord内的命令或关键词触发，调用外部API。
    -   提供一个由自动生成的API密钥保护的安全接口 (`/api/plugins/trigger`)。
    -   允许外部服务（如 IFTTT、Zapier 或自定义脚本）安全地触发你配置的插件。
    -   支持两种动作类型：直接输出API结果，或由LLM进行智能总结后输出，以实现更强大的工具增强型回应。
- **✅ 基于身份组的配置**: 为不同的Discord身份组（Role）分配独特的性格人设、自定义头衔，以及使用额度（消息数/Token数限制）。
- **✅ 额度管理系统**: 内建针对身份组的用量追踪。用户可通过简单的 `!myquota` 命令查询自己剩余的额度。
- **✅ 高级上下文感知**: 机器人能读取聊天历史（数量/字数可配置），以深入理解对话的来龙去脉。
- **✅ 分层人设系统**: 机器人性格由清晰的优先级决定：`特定用户人设 > 身份组人设 > 默认人设`。
- **✅ Docker化，一键部署**: 使用 `docker-compose` 命令，数分钟内即可启动并运行。
- **✅ 多语言界面**: 控制面板支持中/英文即时切换。

## 🛠️ 安装与部署

### 先决条件

- [Docker](https://www.docker.com/get-started)
- [Docker Compose](https://docs.docker.com/compose/install/) (通常随 Docker Desktop 一起安装)

### 安装步骤

1.  **克隆本仓库:**
    ```sh
    git clone https://github.com/RainyN0077/Discord-LLMs-ChatBot.git
    cd Discord-LLMs-ChatBot
    ```

2.  **构建并运行容器:**
    ```sh
    docker-compose up --build -d
    ```
    此命令会自动构建前端和后端镜像，并在后台启动服务。

3.  **配置机器人:**
    - 打开你的浏览器，访问 `http://localhost:8080`。
    - 填写所有必要的配置项，特别是你的**Discord机器人令牌**和**LLM的API密钥**。
    - 你专属的**RESTful API密钥**会自动生成并显示在“全局配置”区域。
    - 浏览不同的配置卡片，根据你的喜好定制机器人。
    - 点击**“保存配置并重启机器人”**。

4.  **大功告成!** 现在可以将你的机器人邀请到你的Discord服务器，开始对话了！试试用 `!myquota` 查询额度，或者触发你配置的插件命令。

## 🔧 配置指南

所有配置均通过 `http://localhost:8080` 的Web界面进行管理。

-   **全局配置 & LLM服务商**: 基础配置。设置你的Discord机器人令牌，选择LLM服务商并输入API密钥。
-   **对话上下文控制**: 定义机器人应该回顾多少条历史消息。可选用适合公共讨论的`频道模式`，或适合个人助理的`记忆模式`。
-   **用户肖像管理**: 为特定用户ID分配自定义称呼和独一无二的性格。此项拥有最高优先级。
-   **基于身份组的配置**:
    -   为拥有特定Discord身份组ID的用户设置专属头衔和人设。
    -   设置消息或Token数限制（例如：每小时100条消息，每天50000 Token）。
    -   自定义额度查询信息框的颜色。
-   **插件管理器**:
    -   点击“添加插件”来创建一个新工具。
    -   为它**命名**，**启用**它，并设置**触发方式**（如 `!weather` 的`命令`，或包含 `搜索` 的`关键词`）。
    -   配置**HTTP请求**（URL、请求方法、请求头等）。你可以使用 `{user_input}` 等占位符。
    -   选择**动作类型**:
        -   `HTTP请求 (直接输出)`: 机器人将直接把API返回的原始文本发出来。
        -   `LLM增强工具`: 机器人会将API的返回结果（用 `{api_result}` 引用）和你自定义的提示词模板一起喂给大模型，生成一段通顺自然的总结。

## 🔌 使用 RESTful API

机器人提供了一个安全的RESTful接口，用于从外部触发插件。

-   **接口地址**: `POST /api/plugins/trigger`
-   **身份验证**: 你必须在请求的 `X-API-Key` 头中包含你唯一的API密钥。你可以在Web控制面板的“全局配置”区域找到并复制你的密钥。
-   **请求体**:
    ```json
    {
      "plugin_name": "你的插件名称",
      "args": {
        "任意键": "任意值",
        "其他键": 123
      }
    }
    ```
    `args` 对象将被转换为JSON字符串，用于替换你插件URL和请求体模板中的 `{user_input}` 占位符。

**cURL 调用示例:**
```sh
curl -X POST http://localhost:8080/api/plugins/trigger \
-H "Content-Type: application/json" \
-H "X-API-Key: 从Web界面获取的API密钥" \
-d '{
  "plugin_name": "天气查询",
  "args": {
    "city": "北京"
  }
}'
```

## 📄 开源许可

本项目采用 **MIT开源许可**。详情请见 [LICENSE](LICENSE) 文件。

</details>