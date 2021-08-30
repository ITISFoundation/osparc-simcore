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

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.Canvas());

    const textArea = this.__textArea = new qx.ui.form.TextArea();
    this.addListener("appear", () => {
      this.__codeArea = osparc.wrapper.CodeMirror.getInstance().convertTextArea(this.__textArea);
    }, this);
    this._add(textArea, {
      top: 0,
      right: 0,
      bottom: 0,
      left: 0
    });
  },

  members: {
    __textArea: null,
    __codeArea: null,

    setValue: function() {
      return this.__codeArea.setValue();
    },

    getValue: function() {
      return this.__codeArea.getValue();
    }
  }
});
