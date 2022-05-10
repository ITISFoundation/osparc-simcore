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

qx.Class.define("osparc.component.form.PortInfoHint", {
  extend: osparc.ui.hint.InfoHint,

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
      if (errorMsg) {
        const baseText = this.getHintText();
        const hintText = baseText + `<p style="color:red;">${errorMsg}</p>`;
        this._hint.setText(hintText);

        this.set({
          source: "@MaterialIcons/error_outline/14",
          textColor: "failed-red"
        });
      } else {
        // back to normal
        const baseText = this.getHintText();
        this._hint.setText(baseText);
        this.set({
          source: "@MaterialIcons/info_outline/14",
          textColor: "text"
        });
      }
    }
  }
});
