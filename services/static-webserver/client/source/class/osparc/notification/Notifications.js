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

qx.Class.define("osparc.notification.Notifications", {
  extend: qx.core.Object,
  type: "singleton",

  construct: function() {
    this.base(arguments);
    this.__notifications = new qx.data.Array();
  },

  statics: {
    __newNotificationBase: function(userId) {
      return {
        "user_id": userId.toString(),
        "user_from_id": osparc.auth.Data.getInstance().getUserId(),
        "date": new Date().toISOString(),
        "product": osparc.product.Utils.getProductName(),
      };
    },

    __newOrganizationObj: function(userId, orgId) {
      const baseNotification = this.__newNotificationBase(userId);
      const specNotification = {
        "category": "NEW_ORGANIZATION",
        "actionable_path": "organization/"+orgId,
        "resource_id": orgId.toString(),
        "title": "New organization",
        "text": "You're now member of a new Organization"
      };
      return {
        ...baseNotification,
        ...specNotification
      };
    },

    __newStudyObj: function(userId, studyId) {
      const study = osparc.product.Utils.getStudyAlias({
        firstUpperCase: true
      });
      const baseNotification = this.__newNotificationBase(userId);
      const specNotification = {
        "category": "STUDY_SHARED",
        "actionable_path": "study/"+studyId,
        "resource_id": studyId,
        "title": `${study} shared`,
        "text": `A ${study} was shared with you`
      };
      return {
        ...baseNotification,
        ...specNotification
      };
    },

    __newTemplateObj: function(userId, templateId) {
      const template = osparc.product.Utils.getTemplateAlias({
        firstUpperCase: true
      });
      const baseNotification = this.__newNotificationBase(userId);
      const specNotification = {
        "category": "TEMPLATE_SHARED",
        "actionable_path": "template/"+templateId,
        "resource_id": templateId,
        "title": `${template} shared`,
        "text": `A ${template} was shared with you`
      };
      return {
        ...baseNotification,
        ...specNotification
      };
    },

    __newAnnotationNoteObj: function(userId, studyId) {
      const baseNotification = this.__newNotificationBase(userId);
      const specNotification = {
        "category": "ANNOTATION_NOTE",
        "actionable_path": "study/"+studyId,
        "resource_id": studyId,
        "title": "Note added",
        "text": "A Note was added for you"
      };
      return {
        ...baseNotification,
        ...specNotification
      };
    },

    __newWalletObj: function(userId, walletId) {
      const baseNotification = this.__newNotificationBase(userId);
      const specNotification = {
        "category": "WALLET_SHARED",
        "actionable_path": "wallet/"+walletId,
        "resource_id": walletId.toString(),
        "title": "Credits shared",
        "text": "A Credit Account was shared with you"
      };
      return {
        ...baseNotification,
        ...specNotification
      };
    },

    postNewOrganization: function(userId, orgId) {
      const params = {
        data: this.__newOrganizationObj(userId, orgId)
      };
      return osparc.data.Resources.fetch("notifications", "post", params);
    },

    postNewStudy: function(userId, studyId) {
      const params = {
        data: this.__newStudyObj(userId, studyId)
      };
      return osparc.data.Resources.fetch("notifications", "post", params);
    },

    postNewTemplate: function(userId, templateId) {
      const params = {
        data: this.__newTemplateObj(userId, templateId)
      };
      return osparc.data.Resources.fetch("notifications", "post", params);
    },

    postNewAnnotationNote: function(userId, studyId) {
      const params = {
        data: this.__newAnnotationNoteObj(userId, studyId)
      };
      return osparc.data.Resources.fetch("notifications", "post", params);
    },

    postNewWallet: function(userId, walletId) {
      const params = {
        data: this.__newWalletObj(userId, walletId)
      };
      return osparc.data.Resources.fetch("notifications", "post", params);
    },

    markAsRead: function(notification) {
      if (notification.isRead() === false) {
        // set as read
        const params = {
          url: {
            notificationId: notification.getId()
          },
          data: {
            "read": true
          }
        };
        osparc.data.Resources.fetch("notifications", "patch", params)
          .then(() => notification.setRead(true))
          .catch(() => notification.setRead(false));
      }
    },
  },

  members: {
    __notifications: null,

    __addNotification: function(notificationObj) {
      const notification = new osparc.notification.Notification(notificationObj);
      this.__notifications.push(notification);
      this.__notifications.sort((a, b) => new Date(b.getDate()) - new Date(a.getDate()));
    },

    addNotifications: function(notifications) {
      this.__notifications.removeAll();
      notifications.forEach(notification => this.__addNotification(notification));
    },

    removeNotification: function(notification) {
      this.__notifications.remove(notification);
    },

    getNotifications: function() {
      return this.__notifications;
    },

    markAllAsRead: function() {
      this.__notifications.forEach(notification => {
        if (notification.isRead() === false) {
          osparc.notification.Notifications.markAsRead(notification);
        }
      });
    },
  }
});
