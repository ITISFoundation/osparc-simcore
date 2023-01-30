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

    if (type) {
      this.setType(type);
    }

    if (closable) {
      this.setClosable(closable);
    }
  },

  properties: {
    type: {
      check: ["maintenance"],
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
      }
      return fullText;
    }
  }
});
