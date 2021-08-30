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

/**
  *
  */

qx.Class.define("osparc.component.node.CodeEditorNodeView", {
  extend: osparc.component.node.BaseNodeView,

  members: {
    __codeEditor: null,

    // overridden
    isSettingsGroupShowable: function() {
      return false;
    },

    // overridden
    _addSettings: function() {
      this.__addCodeEditor();
    },

    // overridden
    _addIFrame: function() {
      return;
    },

    // overridden
    _openEditAccessLevel: function() {
      return;
    },

    // overridden
    _applyNode: function(node) {
      if (!node.isCodeEditor()) {
        console.error("Only code editor nodes are supported");
      }
      this.base(arguments, node);
    },

    __addCodeEditor: function() {
      const node = this.getNode();
      if (!node) {
        return;
      }

      const inputvalues = node.getInputValues();
      const portId = "codeText";
      const codeEditor = this.__codeEditor = new osparc.component.widget.CodeEditor(inputvalues[portId]);
      this._mainView.add(codeEditor, {
        flex: 1
      });
      const propsForm = this.getNode().getPropsForm();
      // eslint-disable-next-line no-underscore-dangle
      const ctrlCodeText = propsForm._form.getControl(portId);
      codeEditor.addListener("changeValue", e => {
        ctrlCodeText.setValue(e.getData());
      }, this);
    }
  }
});
