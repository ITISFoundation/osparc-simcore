/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2022 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.form.PortInfoHint", {
  extend: osparc.ui.hint.InfoHint,

  statics: {
    ERROR_ICON: "@MaterialIcons/error_outline/14"
  },

  properties: {
    portErrorMsg: {
      check: "String",
      init: null,
      nullable: true,
      apply: "__applyPortErrorMsg"
    }
  },

  members: {
    __applyPortErrorMsg: function(errorMsg) {
      let text = this.getHintText();
      if (errorMsg) {
        const color = qx.theme.manager.Color.getInstance().resolve("failed-red");
        text += `<br><br><font color="${color}">${errorMsg}</font>`;
      }
      this._hint.setText(text);
      this.set({
        source: errorMsg ? this.self().ERROR_ICON : osparc.ui.hint.InfoHint.INFO_ICON,
        textColor: errorMsg ? "failed-red" : "text"
      });
    }
  }
});
