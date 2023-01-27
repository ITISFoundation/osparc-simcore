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

  construct: function(text, type = "maintenance") {
    this.base(arguments);

    if (type) {
      this.setType(type);
    }

    if (text) {
      this.setText(text);
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
