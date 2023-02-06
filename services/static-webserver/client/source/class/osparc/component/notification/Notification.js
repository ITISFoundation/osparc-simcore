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

  construct: function(text, type = "maintenance", closable = false) {
    this.base(arguments);

    if (text) {
      this.setText(text);
    }

    this.setType(type);
    this.setClosable(closable);
  },

  properties: {
    type: {
      check: ["maintenance", "smallWindow"],
      init: null,
      nullable: false
    },

    text: {
      check: "String",
      init: "",
      nullable: false
    },

    closable: {
      check: "Boolean",
      init: true,
      nullable: false
    }
  },

  members: {
    getFullText: function(wLineBreak = false) {
      let text = "";
      switch (this.getType()) {
        case "maintenance": {
          text += qx.locale.Manager.tr("Maintenance scheduled.");
          text += wLineBreak ? "<br>" : " ";
          text += this.getText() + ".";
          text += wLineBreak ? "<br>" : " ";
          text += qx.locale.Manager.tr("Please save your work and logout.");
          break;
        }
        case "smallWindow": {
          text += qx.locale.Manager.tr("Oops, your window is a bit small!");
          const width = document.documentElement.clientWidth;
          if (width > 400) {
            text += qx.locale.Manager.tr(" This app performs better for minimum ");
            text += osparc.WindowSizeTracker.MIN_WIDTH + "x" + osparc.WindowSizeTracker.MIN_HEIGHT;
            text += qx.locale.Manager.tr(" window size.");
            text += qx.locale.Manager.tr(" Touchscreen devices are not supported yet.");
          }
          break;
        }
      }
      return text;
    }
  }
});
