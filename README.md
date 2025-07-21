<p>
    <strong>A highly customizable, multi-provider LLM chatbot for Discord with a powerful web UI and a secure, RESTful plugin system.</strong>
    <br />
    <strong>一个高度可定制、支持多服务商、带Web界面和安全RESTful插件系统的Discord大语言模型机器人。</strong>
  </p>

  <table>
    <tr>
      <td align="center">
        <b>Core Settings / 核心设置</b><br>
        <img src="https://cdn.discordapp.com/attachments/1341259395396272180/1395754142068244491/image.png?ex=687b98d7&is=687a4757&hm=c27d1853f6433c4b7f3d005f60655ba68fd3b2e2b01762f6e03e998c64d2b1c2&" alt="Core Settings" width="440">
      </td>
    </tr>
    <tr>
      <td align="center">
        <b>Identity Directives / 身份指令</b><br>
        <img src="https://cdn.discordapp.com/attachments/1341259395396272180/1395754141665726554/image.png?ex=687b98d7&is=687a4757&hm=65fe691f560677fd9550cc7fd6fbe490f12773698e52c7d2e4cddaad4897cb5e&" alt="Identity Directives" width="440">
      </td>
    </tr>
    <tr>
      <td align="center">
        <b>Advanced Tools / 高级工具</b><br>
        <img src="https://cdn.discordapp.com/attachments/1341259395396272180/1395754142550458419/image.png?ex=687b98d7&is=687a4757&hm=26a0ee323e47e9fdbb673852a4fe21057d502a7e0b8a16107ce4db962a9c86f0&" alt="Advanced Tools" width="440">
      </td>
    </tr>
  </table>
</div>

---

<details>
<summary><strong>English Readme (Click to expand)</strong></summary>

## ✨ Features

- **✅ Multi-Provider Support**: Seamlessly switch between **OpenAI** (and compatible APIs), **Google Gemini**, and **Anthropic Claude**.
- **✅ Powerful Web UI**: A comprehensive control panel to configure every aspect of the bot in real-time, including UI customizations like **custom fonts**.
- **✅ Advanced Layered Persona System**: A sophisticated, multi-layered system to define the bot's identity and context awareness with clear priorities.
    -   **Channel/Server Directives**: Set the bot's core identity (`Override` mode) or provide situational context (`Append` mode) for specific channels or entire servers.
    -   **User Portraits**: Define a user's identity *in the eyes of the bot*. This is a top-priority context layer that is *always* respected.
    -   **Role-Based Personas**: Assign the bot a specific persona to use when interacting with users of a certain role.
    -   **Priority Logic**: The bot's final personality is intelligently assembled, not just linearly overridden, ensuring complex and nuanced interactions.
- **✅ 📚 Knowledge Base**: A powerful system to give the bot a persistent memory, managed entirely through the Web UI.
    -   **World Book**: Define keyword-triggered knowledge entries. When a user's message contains a keyword, the corresponding information is injected into the LLM context, making the bot an expert on specific topics.
    -   **Long-term Memory**: Manually add important facts or instructions for the bot to remember permanently across all conversations.
- **✅ 📊 Usage Dashboard & Cost Tracking**:
    -   A comprehensive dashboard to monitor usage statistics and estimate costs in real-time.
    -   Track requests, input/output tokens, and calculate costs with configurable pricing for each model.
    -   Filter and group data by user, role, channel, guild, and various time periods.
- **✅ Secure RESTful Plugin System**:
    -   Create custom tools that call external APIs, triggered by commands or keywords.
    -   Exposes a secure endpoint (`/api/plugins/trigger`) protected by an auto-generated API Key for external service integration (IFTTT, Zapier, etc.).
    -   Supports two action types: direct HTTP output or **LLM-Augmented Tool** for smarter, summarized responses.
- **✅ Quota Management**: Built-in usage tracking and limits (by message count or tokens) for different roles. Users can check their remaining quota with the `!myquota` command, while administrators can monitor all usage on the dashboard.
- **✅ Advanced Context Awareness**: The bot reads chat history (configurable limits) to understand conversations deeply.
- **✅ Real-time Log Viewer**: Monitor bot activities and debug issues directly from the web interface.
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

4.  **You're all set!** Invite your bot to your Discord server and start chatting!

## 🔧 Configuration Guide

All configurations are managed through the web UI at `http://localhost:8080`.

### Core Settings
-   **Global Configuration**: Set your Discord bot token and view your auto-generated API key for external integrations.
-   **LLM Provider**: Choose between OpenAI, Google Gemini, or Anthropic Claude, and configure API keys and models.
-   **Context Control**: Configure how the bot reads and processes chat history (none, channel-based, or memory-based).

### Identity Directives
-   **Channel/Server Directives**:
    -   **Override Mode**: Forces the bot to adopt a specific identity in that context. A Channel Override has the highest priority for the bot's identity.
    -   **Append Mode**: Adds contextual information about the scene (e.g., "This is a casual gaming channel").
-   **User Portraits**: The most important contextual setting. This tells the bot *who the user is* (e.g., "My creator and master"). This information is always provided to the bot.
-   **Role-Based Configuration**:
    -   Defines the bot's persona *towards users* of a specific role (e.g., "Be a respectful butler towards VIPs"). This is a lower-priority identity setting.
    -   Set message or token limits and customize the quota embed color.
-   **Default Behavior**:
     -   Set the bot's foundational, fallback persona.
     -   Customize the message template for when a response is blocked by a content filter (useful for Google Gemini), using `{reason}` as a placeholder.

### Advanced Tools
-   **Knowledge Base**: Manage the bot's persistent memory.
    -   **World Book**: Create and edit keyword-triggered knowledge entries.
    -   **Long-term Memory**: Add and remove general facts for the bot to remember.
-   **Usage Dashboard**: View detailed statistics on token usage, request counts, and estimated costs. You can also configure model pricing here for accurate cost tracking.
-   **Plugin Manager**:
    -   Create tools that trigger on commands or keywords.
    -   **Action Type**: `HTTP Request (Direct Output)` for raw API data, or `LLM-Augmented Tool` to have the LLM summarize the API result (`{api_result}`) for a natural response.
-   **Custom Parameters**: Add custom parameters for fine-tuning your LLM requests (temperature, max_tokens, etc.).
-   **Session Management**: Clear conversation memory for specific channels.
-   **UI Settings**: Load a custom font file (`.ttf`, `.woff`, etc.) to personalize your control panel's appearance. The setting is saved in your browser.

## 🔌 Using the RESTful API

This bot exposes a secure RESTful endpoint to trigger plugins externally.

-   **Endpoint**: `POST /api/plugins/trigger`
-   **Authentication**: Include your unique API Key in the `X-API-Key` header.
-   **Request Body**:
    ```json
    {
      "plugin_name": "Your Plugin Name",
      "args": {
        "any_key": "any_value"
      }
    }
    ```
    The `args` object replaces the `{user_input}` placeholder in your plugin's configuration.

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
- **✅ 强大的Web控制面板**: 一个全面的网页控制台，无需接触代码即可实时配置机器人的方方面面，甚至包括**自定义界面字体**等个性化设置。
- **✅ 高级分层人设系统**: 一个精密、多层级的系统，用清晰的优先级逻辑来定义机器人的身份和场景感知能力。
    -   **频道/服务器指令**: 可为特定频道或整个服务器设定Bot的核心身份（`覆盖`模式），或提供场景上下文（`追加`模式）。
    -   **用户肖像**: 定义用户在Bot眼中的身份。这是一个永远被遵守的、最高优先级的上下文层。
    -   **基于身份组的人设**: 为Bot设定在与特定身份组成员互动时应有的人设。
    -   **优先级逻辑**: Bot的最终性格是智能组装而成，而非简单的线性覆盖，确保了复杂且细致入微的互动。
- **✅ 📚 知识库系统**: 一个强大的系统，赋予机器人持久的记忆，完全通过Web UI进行管理。
    -   **世界设定集 (World Book)**: 定义由关键词触发的知识条目。当用户消息包含关键词时，相应的信息会被注入到LLM的上下文中，让机器人成为特定主题的专家。
    -   **长期记忆 (Long-term Memory)**: 手动添加重要的事实或指令，让机器人可以跨越不同对话永久记住它们。
- **✅ 📊 用量仪表盘 & 成本追踪**:
    -   一个全面的仪表盘，用于实时监控用量统计数据和估算成本。
    -   可追踪请求数、输入/输出Token数，并基于每个模型可配置的价格来计算成本。
    -   支持按用户、身份组、频道、服务器以及不同时间周期（今日、本周、本月、全部）进行数据筛选和分组。
- **✅ 安全的RESTful插件系统**:
    -   创建自定义工具，通过命令或关键词触发，并调用外部API。
    -   提供一个由自动生成的API密钥保护的安全接口 (`/api/plugins/trigger`)，便于与外部服务（如 IFTTT、Zapier）集成。
    -   支持两种动作类型：直接输出API结果，或使用 **LLM增强工具** 对结果进行智能总结，生成更自然的回应。
- **✅ 额度管理系统**: 内建针对身份组的用量追踪和限制（按消息数或Token数）。用户可通过 `!myquota` 命令查询自己剩余的额度，同时管理员可以在仪表盘上监控所有用量。
- **✅ 高级上下文感知**: 机器人能读取聊天历史（数量/字数可配置），以深入理解对话的来龙去脉。
- **✅ 实时日志查看器**: 直接从Web界面监控机器人活动并调试问题。
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
    此命令会自动构建前后端镜像，并在后台启动服务。

3.  **配置机器人:**
    - 打开你的浏览器，访问 `http://localhost:8080`。
    - 填写所有必要的配置项，特别是你的**Discord机器人令牌**和**LLM的API密钥**。
    - 你专属的**RESTful API密钥**会自动生成并显示在"全局配置"区域。
    - 浏览不同的配置卡片，根据你的喜好定制机器人。
    - 点击**"保存配置并重启机器人"**。

4.  **大功成告!** 现在可以将你的机器人邀请到你的Discord服务器，开始对话了！

## 🔧 配置指南

所有配置均通过 `http://localhost:8080` 的Web界面进行管理。

### 核心设置
-   **全局配置**: 设置你的Discord机器人令牌，并查看自动生成的API密钥用于外部集成。
-   **大模型服务商**: 在OpenAI、Google Gemini或Anthropic Claude之间选择，并配置API密钥和模型。
-   **上下文控制**: 配置机器人如何读取和处理聊天历史（无、基于频道或基于记忆）。

### 身份指令
-   **频道/服务器指令**:
    -   **覆盖模式**: 强制Bot在该场景下扮演一个特定身份。频道覆盖是Bot身份的最高优先级指令。
    -   **追加模式**: 为对话添加场景背景信息（例如："这是一个闲聊吹水频道"）。
-   **用户肖像**: 最重要的上下文设定。这部分是告诉Bot"**用户是谁**"（例如："我的创造者和主人"）。Bot会永远将此信息纳入考量。
-   **基于身份组的配置**:
    -   定义Bot**对待**特定身份组用户的态度和人设（例如："对VIP用户要像管家一样恭敬"）。这是一个较低优先级的身份设定。
    -   可设置消息或Token数限制，并自定义额度查询信息框的颜色。
-   **默认行为**:
    -   设定Bot的基础、备用人设。
    -   自定义当响应被内容过滤器（主要针对Google Gemini）屏蔽时发送的回复消息模板，可使用 `{reason}` 作为原因占位符。

### 高级工具
-   **知识库**: 管理机器人的持久记忆。
    -   **世界设定集**: 创建并编辑基于关键词的知识条目。
    -   **长期记忆**: 添加和删除机器人需要记住的通用事实。
-   **用量仪表盘**: 查看关于Token用量、请求次数和估算成本的详细统计数据。你还可以在此配置模型价格以进行精确的成本追踪。
-   **插件管理器**:
    -   创建由命令或关键词触发的工具。
    -   **动作类型**: `HTTP请求 (直接输出)`用于返回原始API数据；`LLM增强工具`则会让大模型总结API结果（用`{api_result}`引用），以生成更自然的回应。
-   **自定义参数**: 添加自定义参数以微调你的LLM请求（temperature、max_tokens等）。
-   **会话管理**: 清除特定频道的对话记忆。
-   **界面设置**: 加载自定义字体文件（如 `.ttf`, `.woff`），个性化你的控制面板外观。该设置会保存在你的浏览器中。

## 🔌 使用 RESTful API

机器人提供了一个安全的RESTful接口，用于从外部触发插件。

-   **接口地址**: `POST /api/plugins/trigger`
-   **身份验证**: 必须在请求的 `X-API-Key` 头中包含你唯一的API密钥。
-   **请求体**:
    ```json
    {
      "plugin_name": "你的插件名称",
      "args": {
        "任意键": "任意值"
      }
    }
    ```
    `args` 对象将替换你插件配置中的 `{user_input}` 占位符。

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