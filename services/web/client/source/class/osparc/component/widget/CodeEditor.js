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
  extend: osparc.component.widget.TextEditor,

  members: {
    __codeArea: null,

    _populateTextArea: function() {
      this.base(arguments);
      this.addListener("appear", () => {
        this.__codeArea = osparc.wrapper.CodeMirror.getInstance().convertTextArea(this.__textArea);
      }, this);
    },

    getValue: function() {
      return this.__codeArea.getValue();
    }
  }
});
