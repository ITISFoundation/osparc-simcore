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


qx.Class.define("osparc.workbench.ConversationUI", {
  extend: osparc.workbench.BaseNodeUI,

  construct: function(conversationData) {
    this.base(arguments);

    this.__conversationData = conversationData;

    const captionTitle = this.getChildControl("title");
    captionTitle.set({
      value: conversationData.title || this.tr("Conversation"),
    });
  },

  members: {
    __conversationData: null,
  },
});
