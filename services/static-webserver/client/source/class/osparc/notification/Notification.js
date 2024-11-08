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

qx.Class.define("osparc.notification.Notification", {
  extend: qx.core.Object,

  construct: function(notificationObj) {
    this.base(arguments);

    this.set({
      id: notificationObj.id,
      resourceId: notificationObj.resource_id ? notificationObj.resource_id : null,
      category: notificationObj.category,
      actionablePath: notificationObj.actionable_path,
      title: notificationObj.title,
      text: notificationObj.text,
      userFromId: notificationObj.user_from_id ? notificationObj.user_from_id : null,
      date: new Date(notificationObj.date),
      read: ["true", "True", true].includes(notificationObj.read)
    });
  },

  properties: {
    id: {
      check: "String",
      init: null,
      nullable: false,
      event: "changeId"
    },

    resourceId: {
      check: "String",
      init: null,
      nullable: true,
      event: "changeResourceId"
    },

    category: {
      check: [
        "NEW_ORGANIZATION",
        "STUDY_SHARED",
        "TEMPLATE_SHARED",
        "ANNOTATION_NOTE",
        "WALLET_SHARED"
      ],
      init: null,
      nullable: false,
      event: "changeCategory"
    },

    actionablePath: {
      check: "String",
      init: null,
      nullable: false,
      event: "changeActionablePath"
    },

    title: {
      check: "String",
      init: null,
      nullable: false,
      event: "changeTitle"
    },

    text: {
      check: "String",
      init: null,
      nullable: false,
      event: "changeText"
    },

    userFromId: {
      check: "Number",
      init: null,
      nullable: true,
      event: "changeUserFromId"
    },

    date: {
      check: "Date",
      init: null,
      nullable: false,
      event: "changeDate"
    },

    read: {
      check: "Boolean",
      init: false,
      nullable: false,
      event: "changeRead"
    }
  }
});
