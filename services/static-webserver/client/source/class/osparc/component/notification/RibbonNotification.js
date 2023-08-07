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

qx.Class.define("osparc.component.notification.RibbonNotification", {
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
      check: ["maintenance", "smallWindow", "announcement"],
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
      let fullText = "";
      switch (this.getType()) {
        case "maintenance": {
          fullText += qx.locale.Manager.tr("Maintenance scheduled.");
          fullText += wLineBreak ? "<br>" : " ";
          fullText += this.getText() + ".";
          fullText += wLineBreak ? "<br>" : " ";
          fullText += qx.locale.Manager.tr("Please save your work and logout.");
          break;
        }
        case "smallWindow": {
          fullText += qx.locale.Manager.tr("Oops, your window is a bit small!");
          const longText = this.getText();
          if (longText) {
            fullText += " " + longText;
          }
          break;
        }
        case "announcement": {
          const longText = this.getText();
          if (longText) {
            fullText += " " + longText;
          }
          if (!wLineBreak) {
            fullText = fullText.replace(/<br\s*\/?>/gi, " ");
          }
          break;
        }
      }
      return fullText;
    }
  }
});
