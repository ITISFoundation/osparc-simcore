/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */


qx.Class.define("osparc.study.Conversation", {
  extend: osparc.conversation.MessageList,

  /**
    * @param studyData {String} Study Data
    * @param conversation {osparc.data.model.Conversation} Conversation
    */
  construct: function(studyData, conversation) {
    this.__studyData = studyData;
    this.base(arguments, conversation);
  },

  members: {
    __studyData: null,

    _buildLayout: function() {
      this.base(arguments);

      const addMessage = this.getChildControl("add-message").set({
        studyData: this.__studyData,
        enabled: osparc.data.model.Study.canIWrite(this.__studyData["accessRights"]),
      });
      addMessage.addListener("addMessage", e => {
        const content = e.getData();
        const conversation = this.getConversation();
        if (conversation) {
          this.__postMessage(content);
        } else {
          // create new conversation first
          osparc.store.ConversationsProject.getInstance().postConversation(this.__studyData["uuid"])
            .then(data => {
              const newConversation = new osparc.data.model.ConversationProject(data, this.__studyData["uuid"]);
              this.setConversation(newConversation);
              this.__postMessage(content);
            });
        }
      });
      addMessage.addListener("notifyUser", e => {
        const userGid = e.getData();
        const conversation = this.getConversation();
        if (conversation) {
          this.__postNotify(userGid);
        } else {
          // create new conversation first
          osparc.store.ConversationsProject.getInstance().postConversation(this.__studyData["uuid"])
            .then(data => {
              const newConversation = new osparc.data.model.ConversationProject(data, this.__studyData["uuid"]);
              this.setConversation(newConversation);
              this.__postNotify(userGid);
            });
        }
      });
    },

    // overridden
    _createMessageUI: function(message) {
      const messageUI = new osparc.conversation.MessageUI(message, this.__studyData);
      messageUI.getChildControl("message-content").set({
        measurerMaxWidth: 400,
      });
      return messageUI;
    },

    __postMessage: function(content) {
      const conversationId = this.getConversation().getConversationId();
      osparc.store.ConversationsProject.getInstance().postMessage(this.__studyData["uuid"], conversationId, content);
    },

    __postNotify: function(userGid) {
      const conversationId = this.getConversation().getConversationId();
      osparc.store.ConversationsProject.getInstance().notifyUser(this.__studyData["uuid"], conversationId, userGid)
        .then(data => {
          this.fireDataEvent("messageAdded", data);
          const potentialCollaborators = osparc.store.Groups.getInstance().getPotentialCollaborators();
          if (userGid in potentialCollaborators) {
            if ("getUserId" in potentialCollaborators[userGid]) {
              const uid = potentialCollaborators[userGid].getUserId();
              osparc.notification.Notifications.pushConversationNotification(uid, this.__studyData["uuid"]);
            }
            const msg = "getLabel" in potentialCollaborators[userGid] ? potentialCollaborators[userGid].getLabel() + this.tr(" was notified") : this.tr("Notification sent");
            osparc.FlashMessenger.logAs(msg, "INFO");
          }
        });
    },
  }
});
