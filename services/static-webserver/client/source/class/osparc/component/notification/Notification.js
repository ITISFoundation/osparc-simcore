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

qx.Class.define("osparc.component.notification.Notification", {
  extend: qx.core.Object,

  construct: function(notificationObj) {
    this.base(arguments);

    this.set({
      id: notificationObj.id,
      category: notificationObj.category,
      actionablePath: notificationObj.actionable_path,
      title: notificationObj.title,
      text: notificationObj.text,
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

    category: {
      check: [
        "NEW_ORGANIZATION",
        "STUDY_SHARED",
        "TEMPLATE_SHARED",
        "ANNOTATION_NOTE"
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
