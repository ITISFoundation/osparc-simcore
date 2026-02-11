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

    sendEmail: function(recipients, subject, bodyHtml, bodyText) {
      console.log("Faker sending email: ", subject, " to ", recipients);
      console.log("Body HTML: ", bodyHtml);
      console.log("Body Text: ", bodyText);
      return new Promise((resolve) => resolve());
    },
  }
});
