/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2021 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.component.widget.CodeEditor", {
  extend: qx.ui.core.Widget,

  construct: function(initCode) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.Canvas());

    const textArea = new qx.ui.form.TextArea(initCode);
    this.addListener("appear", () => {
      const codeArea = osparc.wrapper.CodeMirror.getInstance().convertTextArea(textArea);
      codeArea.on("change", cm => {
        const value = cm.getValue();
        this.setValue(value);
      });
    }, this);
    this._add(textArea, {
      top: 0,
      right: 0,
      bottom: 0,
      left: 0
    });
  },

  properties: {
    value: {
      check: "String",
      nullable: false,
      init: "",
      event: "changeValue"
    }
  }
});
