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

/**
 * Class that stores Project Conversation data.
 */

qx.Class.define("osparc.data.model.ConversationProject", {
  extend: osparc.data.model.Conversation,

  /**
   * @param conversationData {Object} Object containing the serialized Conversation Data
   * @param studyId {String} ID of the Study
   * */
  construct: function(conversationData, studyId) {
    this.base(arguments, conversationData);

    this.set({
      studyId: studyId || null,
    });
  },

  properties: {
    studyId: {
      check: "String",
      nullable: true,
      init: null,
    },
  },
});
