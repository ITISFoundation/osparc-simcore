/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2025 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.store.Faker", {
  extend: qx.core.Object,
  type: "singleton",

  statics: {
    // spellchecker:off
    IDK: [
      "Ez dakit",
      "No lo sé",
      "I don't know",
      "Eu não sei",
      "I weiss nöd",
      "Je ne sais pas",
      "Non lo so",
      "Ich weiß nicht",
      "Jeg ved det ikke",
      "Я не знаю",
      "Ik weet ni",
      "Neviem",
    ],
    // spellchecker:on
  },

  members: {
    sendSocketMessageToMyself: function(eventName, message) {
      const socket = osparc.wrapper.WebSocket.getInstance().getSocket();
      if (socket) {
        const listeners = socket.listeners(eventName);
        listeners.forEach(fn => fn(message));
      }
    },

    triggerChatbot: function(conversationId, messageId) {
      // wait a random time between 3 and 6 seconds to simulate building response
      const delay = 3000 + Math.floor(Math.random() * 3000);
      setTimeout(() => {
        // create a fake chatbot response
        const randomIdx = Math.floor(Math.random() * this.self().IDK.length);
        const chatbotResponse = this.self().IDK[randomIdx];
        const chatbot = osparc.store.Groups.getInstance().getChatbot();
        const now = new Date().toISOString();
        const messageData = {
          content: chatbotResponse,
          conversationId,
          created: now,
          messageId: osparc.utils.Utils.uuidV4(),
          modified: now,
          type: "MESSAGE",
          userGroupId: chatbot.getGroupId(),
        };

        // and send a CONVERSATION_MESSAGE_CREATED websocket message to myself
        this.sendSocketMessageToMyself(
          osparc.data.model.Conversation.CHANNELS.CONVERSATION_MESSAGE_CREATED,
          messageData
        );
      }, delay);

      return new Promise((resolve) => resolve());
    },

    fetchEmailTemplates: function() {
      const templates = [{
        "ref": {
          "channel": "email",
          "templateName": "empty-email",
        },
        "contextSchema": {}
      }];
      return new Promise((resolve) => resolve(templates));
    },

    fetchEmailPreview: function(templateName, context) {
      console.log("Faker fetching email preview for template:", templateName, "with context:", context);
      const preview = {
        "ref": {
          "channel": "email",
          "templateName": "empty-email"
        },
        "content": {
          "subject": "sdfasdf",
          "bodyHtml": `
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title></title>
<style>
  body {
      font-family: Manrope, sans-serif;
      margin: 0;
      padding: 0;
      background-color: #f4f4f4;
  }
  .email-container {
      max-width: 600px;
      margin: 20px auto;
      background-color: #ffffff;
      padding: 20px;
      border-radius: 8px;
      box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
  }
  .header {
      display: flex;
      align-items: center;
      border-bottom: 2px solid #ddd;
      padding-bottom: 10px;
      margin-bottom: 20px;
  }
  .logo {
      height: 40px;
  }
  .content {
      color: #333;
      font-size: 16px;
      line-height: 1.5;
  }
  a {
      color: #007bff;
      text-decoration: none;
  }
  .strong-button {
      cursor: pointer;
      background-color: rgb(0, 144, 208);
      color: white;
      padding: 10px;
      border: none;
      border-radius: 4px;
      overflow: hidden;
      white-space: nowrap;
      user-select: none;
      touch-action: none;
      outline: none;
  }
  .strong-button a {
      font-size: 16px;
      color: white;
      text-decoration: none;
      display: block;
      width: 100%;
      height: 100%;
      text-align: center;
  }
  .footer {
      margin-top: 20px;
      padding-top: 15px;
      border-top: 2px solid #ddd;
      font-size: 14px;
      text-align: center;
      color: #666;
  }
  .footer a {
      color: #007bff;
      text-decoration: none;
  }
  .github-logo {
    height: 20px;
    vertical-align: bottom;
  }
</style>
</head>
<body>
  <div class="email-container">
    <div class="header">
      <a href="https://sim4life.io/" target="_blank" rel="noopener noreferrer">
        <img src="https://raw.githubusercontent.com/ITISFoundation/osparc-simcore/refs/heads/master/services/static-webserver/client/source/resource/osparc/Sim4Life_full_logo_black.svg" alt="Logo" class="logo">
      </a>
    </div>
    <div class="content">
      <p>Hello <b>username</b>,</p>
      <p>This is a free-form email template. You can customize the content as needed.</p>
      <p>Best regards,<br>The <i>oSPARC Team</i></p>
    </div>
    <div class="footer">
      <p>
        Visit the <a href="https://sim4life.io/" target="_blank" rel="noopener noreferrer">Platform</a> |
        Need help? <a href="mailto:support@sim4life.io">Support</a> |
        Powered by oSPARC
        <a href="https://github.com/ITISFoundation/osparc-simcore" target="_blank" rel="noopener noreferrer">
          <img src="https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png" alt="GitHub" class="github-logo">
        </a>
      </p>
    </div>
  </div>
</body>
</html>
`,
          "bodyText": "Hello username,\n\nThis is a free-form email template. You can customize the content as needed.\n\nBest regards,\nThe oSPARC Team"
        },
      };

      return new Promise((resolve) => resolve(preview));
    },

    sendEmail: function(recipients, subject, bodyHtml, bodyText) {
      console.log("Faker sending email: ", subject, " to ", recipients);
      console.log("Body HTML: ", bodyHtml);
      console.log("Body Text: ", bodyText);
      return new Promise((resolve) => resolve());
    },
  }
});
