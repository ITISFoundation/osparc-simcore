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
  },
  members: {
    triggerChatbot: function(conversationId, messageId) {
      // wait a random time between 2 and 5 seconds to simulate building response
      const delay = 2000 + Math.floor(Math.random() * 3000);
      setTimeout(() => {
        // create a fake chatbot response
        const randomIdx = Math.floor(Math.random() * this.self().IDK.length);
        const chatbotResponse = this.self().IDK[randomIdx];
        const chatbot = osparc.store.Groups.getInstance().getChatbot();
        const messageData = {
          content: chatbotResponse,
          conversationId,
          created: new Date().toISOString(),
          messageId: osparc.utils.Utils.uuidV4(),
          modified: new Date().toISOString(),
          type: "MESSAGE",
          userGroupId: chatbot.getGroupId(),
        };

        // and send a CONVERSATION_MESSAGE_CREATED websocket message to myself
        const socket = osparc.wrapper.WebSocket.getInstance();
        // todo
      }, delay);
    },
  }
});
