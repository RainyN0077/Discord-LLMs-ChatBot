<div align="center">
  <h1>Discord LLM Chatbot 🤖</h1>
  <p>
    A highly customizable, multi-provider LLM chatbot for Discord with a powerful web UI.
    <br />
    一个高度可定制、支持多服务商、带Web界面的Discord大语言模型机器人。
  </p>
  <table>
    <tr>
      <td>
        <img src="https://cdn.discordapp.com/attachments/1341259395396272180/1394873127774720121/image.png?ex=68786455&is=687712d5&hm=0d2976722cf2dff04e37ff70f13bf4a1701374c3bb670c553b45169bbd7a3150&" alt="Web UI Overview" width="440">
      </td>
      <td>
        <img src="https://cdn.discordapp.com/attachments/1341259395396272180/1394873127384780820/image.png?ex=68786455&is=687712d5&hm=da5929e5e35208ab422194cab6b4a51c9994ad40654a4d77854793bacd886232&" alt="Configuration Detail" width="440">
      </td>
    </tr>
  </table>
</div>
 
---
 
<details>
<summary><strong>English Readme (Click to expand)</strong></summary>

## ✨ Features

- **✅ Multi-Provider Support**: Seamlessly switch between OpenAI (and compatible APIs), Google Gemini, and Anthropic Claude.
- **✅ Web UI Control Panel**: Easy-to-use web interface to configure everything without touching code.
- **✅ Advanced Context Awareness**: Bot reads chat history (configurable limits) to understand conversations.
- **✅ Robust Identity System**: Accurately identifies all users in conversations, preventing identity confusion even with duplicate nicknames.
- **✅ User-Specific Portraits**: Assign custom nicknames and personality prompts to different users for personalized interactions.
- **✅ Mention Awareness**: Understands who is being mentioned in a message and injects their identity into the context.
- **✅ Dockerized**: Easy to set up and run with Docker and Docker Compose.
- **✅ Multilingual UI**: Switch between English and Chinese on the fly within the control panel.

## 🛠️ Setup & Installation

### Prerequisites

- [Docker](https://www.docker.com/get-started)
- [Docker Compose](https://docs.docker.com/compose/install/)

### Installation

1.  **Clone the repository:**
    ```sh
    git clone https://github.com/YourUsername/YourRepoName.git
    cd YourRepoName
    ```

2.  **Build and run the containers:**
    ```sh
    docker-compose up --build -d
    ```

3.  **Configure the bot:**
    - Open your web browser and navigate to `http://localhost:8080`.
    - Fill in all the required configurations, especially your **Discord Bot Token** and **LLM API Key**.
    - Click **"Save Configuration & Restart Bot"**.

4.  **You're all set!** Invite your bot to your Discord server and start chatting!

## 🔧 Configuration Guide

All configurations are managed through the web UI at `http://localhost:8080`.

- **Global Configuration**: Set your unique Discord Bot Token.
- **LLM Provider**: Choose your LLM provider and enter the corresponding API Key. For OpenAI-compatible APIs, an optional Base URL can be provided.
- **Conversation Context Control**: Define how many past messages (e.g., 20) and the total character limit (e.g., 4000) the bot should read for context.
- **User Portraits**: Assign custom nicknames and unique personalities to specific user IDs. This allows the bot to interact with different users in different ways.
- **Default Behavior**: Set the bot's default personality (system prompt), trigger words (e.g., `jarvis, ask`), and response mode (Stream/Non-Stream).

## 📄 License

This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for details.

</details>

<br>

<details open>
<summary><strong>中文说明 (点击展开)</strong></summary>

## ✨ 功能特性

- **✅ 多服务商支持**: 可在 OpenAI (及兼容API)、Google Gemini、Anthropic Claude 之间无缝切换。
- **✅ Web用户界面控制面板**: 无需接触代码，通过简单易用的网页即可完成所有配置。
- **✅ 高级上下文感知**: 机器人能读取聊天历史（数量/字数可配置），理解对话的来龙去脉。
- **✅ 稳健的身份系统**: 能精准识别对话中的所有用户，即使面对重复的昵称也能防止身份混淆。
- **✅ 用户专属肖像**: 可为不同用户分配自定义的称呼和独特的性格（人设），实现真正的个性化互动。
- **✅ 提及(Mention)感知**: 能理解消息中提及了哪些用户，并将他们的身份注入上下文。
- **✅ Docker化**: 使用 Docker 和 Docker Compose，一键部署，轻松运行。
- **✅ 多语言界面**: 控制面板支持中/英文即时切换。

## 🛠️ 安装与部署

### 先决条件

- [Docker](https://www.docker.com/get-started)
- [Docker Compose](https://docs.docker.com/compose/install/) (通常随 Docker Desktop 一起安装)

### 安装步骤

1.  **克隆本仓库:**
    ```sh
    git clone https://github.com/YourUsername/YourRepoName.git
    cd YourRepoName
    ```

2.  **构建并运行容器:**
    ```sh
    docker-compose up --build -d
    ```
    此命令会自动构建前端和后端镜像，并在后台启动服务。

3.  **配置机器人:**
    - 打开你的浏览器，访问 `http://localhost:8080`。
    - 填写所有必要的配置项，特别是你的**Discord机器人令牌**和**LLM的API密钥**。
    - 点击**“保存配置并重启机器人”**。

4.  **大功告成!** 现在可以将你的机器人邀请到你的Discord服务器，开始对话了！

## 🔧 配置指南

所有配置均通过 `http://localhost:8080` 的Web界面进行管理。

- **全局配置**: 设置你唯一的Discord机器人令牌。
- **LLM服务商配置**: 选择你的LLM服务商并输入对应的API密钥。对于兼容OpenAI的API，可以额外提供一个代理URL (Base URL)。
- **对话上下文控制**: 定义机器人应该回顾多少条历史消息（例如20条）以及总的字数上限（例如4000字）来联系上下文。
- **用户肖像管理**: 为特定的用户ID分配自定义的称呼和独特的性格。这能让机器人以不同的方式与不同用户互动。
- **默认模型与行为**: 设置机器人的默认性格（系统提示词）、触发词（例如 `贾维斯, 问`）以及回应模式（流式/非流式）。

## 📄 开源许可

本项目采用 **MIT开源许可**。详情请见 [LICENSE](LICENSE) 文件。

</details>