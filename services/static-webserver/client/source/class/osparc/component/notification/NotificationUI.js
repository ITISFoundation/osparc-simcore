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

qx.Class.define("osparc.component.notification.NotificationUI", {
  extend: qx.ui.core.Widget,

  construct: function(notification) {
    this.base(arguments);

    this.set({
      maxWidth: this.self().MAX_WIDTH,
      padding: this.self().PADDING,
      cursor: "pointer"
    });

    const layout = new qx.ui.layout.Grid(10, 3);
    layout.setColumnAlign(0, "center", "middle");
    layout.setColumnAlign(1, "left", "middle");
    layout.setColumnFlex(1, 1);
    this._setLayout(layout);

    this.bind("read", this, "backgroundColor", {
      converter: read => read ? "background-main-3" : "background-main-4"
    });

    if (notification) {
      this.setNotification(notification);
    }

    this.addListener("tap", () => this.__notificationTapped());
  },

  events: {
    "notificationTapped": "qx.event.type.Event"
  },

  properties: {
    notification: {
      check: "osparc.component.notification.Notification",
      init: null,
      nullable: false,
      apply: "__applyNotification"
    }
  },

  statics: {
    MAX_WIDTH: 300,
    PADDING: 10
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "icon":
          control = new qx.ui.basic.Image().set({
            source: "@FontAwesome5Solid/paw/14",
            alignX: "center",
            alignY: "middle",
            minWidth: 18
          });
          this._add(control, {
            row: 0,
            column: 0,
            rowSpan: 3
          });
          break;
        case "title":
          control = new qx.ui.basic.Label().set({
            font: "text-13",
            rich: true,
            wrap: true
          });
          this._add(control, {
            row: 0,
            column: 1
          });
          break;
        case "text":
          control = new qx.ui.basic.Label().set({
            font: "text-12",
            rich: true,
            wrap: true
          });
          this._add(control, {
            row: 1,
            column: 1
          });
          break;
        case "date":
          control = new qx.ui.basic.Label().set({
            font: "text-11",
            rich: true,
            wrap: true
          });
          this._add(control, {
            row: 2,
            column: 1
          });
          break;
      }
      return control || this.base(arguments, id);
    },

    __applyNotification: function(notification) {
      const icon = this.getChildControl("icon");
      notification.bind("category", icon, "source", {
        converter: value => {
          let source = "";
          switch (value) {
            case "new_organization":
              source = "@FontAwesome5Solid/users/14";
              break;
            case "study_shared":
              source = "@FontAwesome5Solid/file/14";
              break;
            case "template_shared":
              source = "@FontAwesome5Solid/copy/14";
              break;
          }
          return source;
        }
      });

      const title = this.getChildControl("title");
      notification.bind("title", title, "value");

      const text = this.getChildControl("text");
      notification.bind("text", text, "value");

      const date = this.getChildControl("date");
      notification.bind("date", date, "value", {
        converter: value => {
          if (value) {
            return osparc.utils.Utils.formatDateAndTime(new Date(value));
          }
          return "";
        }
      });
    },

    __notificationTapped: function() {
      const notification = this.getNotification();
      if (!notification) {
        return;
      }

      this.fireEvent("notificationTapped");

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

      // open actionable path
      const actionablePath = notification.getActionablePath();
      const category = notification.getCategory();
      switch (category) {
        case "new_organization": {
          const items = actionablePath.split("/");
          const orgId = items.pop();
          console.log("open details", orgId);
          const preferencesWindow = osparc.desktop.preferences.PreferencesWindow.openWindow();
          preferencesWindow.openOrganizations();
          break;
        }
        case "study_shared":
          console.log(actionablePath);
          break;
        case "template_shared":
          console.log(actionablePath);
          break;
      }
    }
  }
});
