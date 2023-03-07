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

qx.Class.define("osparc.component.notification.Notifications", {
  extend: qx.core.Object,
  type: "singleton",

  construct: function() {
    this.base(arguments);
    this.__notifications = new qx.data.Array();
  },

  statics: {
    newOrganizationObj: function(userId, orgId) {
      return {
        "user_id": userId.toString(),
        "category": "new_organization",
        "actionable_path": "organization/"+orgId,
        "title": qx.locale.Manager.tr("New organization"),
        "text": qx.locale.Manager.tr("You're now member of a new Organization"),
        "date": new Date().toISOString()
      };
    },

    newStudyObj: function(userId, orgId) {
      return {
        "user_id": userId.toString(),
        "category": "study_shared",
        "actionable_path": "study/"+orgId,
        "title": qx.locale.Manager.tr("Study shared"),
        "text": qx.locale.Manager.tr("A study was shared with you"),
        "date": new Date().toISOString()
      };
    },

    newTemplateObj: function(userId, orgId) {
      return {
        "user_id": userId.toString(),
        "category": "template_shared",
        "actionable_path": "template/"+orgId,
        "title": qx.locale.Manager.tr("Template shared"),
        "text": qx.locale.Manager.tr("A template was shared with you"),
        "date": new Date().toISOString()
      };
    }
  },

  members: {
    __notifications: null,

    postNewOrganization: function(userId, orgId) {
      const params = {
        data: osparc.component.notification.Notifications.newOrganizationObj(userId, orgId)
      };
      osparc.data.Resources.fetch("notifications", "post", params);
    },

    postNewStudy: function(userId, orgId) {
      const params = {
        data: osparc.component.notification.Notifications.newStudyObj(userId, orgId)
      };
      osparc.data.Resources.fetch("notifications", "post", params);
    },

    postNewTemplate: function(userId, orgId) {
      const params = {
        data: osparc.component.notification.Notifications.newTemplateObj(userId, orgId)
      };
      osparc.data.Resources.fetch("notifications", "post", params);
    },


    addNotification: function(notificationObj) {
      const notification = new osparc.component.notification.Notification(notificationObj);
      this.__notifications.push(notification);
      this.__notifications.sort((a, b) => new Date(b.getDate()) - new Date(a.getDate()));
    },

    addNotifications: function(notifications) {
      notifications.forEach(notification => this.addNotification(notification));
    },

    removeNotification: function(notification) {
      this.__notifications.remove(notification);
    },

    getNotifications: function() {
      return this.__notifications;
    }
  }
});
