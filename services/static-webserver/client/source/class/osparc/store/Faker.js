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
      "Non lo so",
      "Je ne sais pas",
      "Ich weiß nicht",
      "Δεν ξέρω",
      "わかりません",
    ],
  },
  members: {
    triggerChatbot: function(conversationId, messageId) {
      const randomIdx = Math.floor(Math.random() * this.self().IDK.length);
      const chatbotResponse = this.self().IDK[randomIdx];
      return osparc.store.ConversationsSupport.getInstance().postMessage(
        conversationId,
        chatbotResponse,
        messageId,
      );
    },
  }
});
