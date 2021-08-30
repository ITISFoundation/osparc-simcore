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
      this._settingsLayout.removeAll();

      const node = this.getNode();
      const propsForm = node.getPropsForm();
      if (propsForm && Object.keys(node.getInputs()).length) {
        propsForm.addListener("changeChildVisibility", () => {
          this.__checkSettingsVisibility();
        }, this);
        this._settingsLayout.add(propsForm);
      }
      this.__checkSettingsVisibility();

      this._addToMainView(this._settingsLayout);

      this.__addCodeEditor();
    },

    __checkSettingsVisibility: function() {
      const isSettingsGroupShowable = this.isSettingsGroupShowable();
      this._settingsLayout.setVisibility(isSettingsGroupShowable ? "visible" : "excluded");
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

      const codeEditor = this.__codeEditor = new osparc.component.widget.CodeEditor();
      this._mainView.add(codeEditor, {
        flex: 1
      });
    }
  }
});
