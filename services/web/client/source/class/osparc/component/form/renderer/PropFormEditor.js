/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2020 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */


qx.Class.define("osparc.component.form.renderer.PropFormEditor", {
  extend: osparc.component.form.renderer.PropFormBase,

  /**
   * create a page for the View Tab with the given title
   *
   * @param form {osparc.component.form.Auto} form widget to embedd
   * @param node {osparc.data.model.Node} Node owning the widget
   */
  construct: function(form, node) {
    this.base(arguments, form, node);

    this.__ctrlRBsMap = {};
    this.__addAccessLevelRBs();
  },

  // eslint-disable-next-line qx-rules/no-refs-in-members
  members: {
    // overridden
    _gridPos: {
      label: 0,
      ctrlField: 1,
      accessLevel: 2
    },
    _accessLevel: {
      hidden: 0,
      readOnly: 1,
      readAndWrite: 2
    },

    __ctrlRBsMap: null,

    // overridden
    setAccessLevel: function(data) {
      for (const key in data) {
        const control = this.__getRadioButtonsFieldChild(key);
        if (control) {
          const group = this.__ctrlRBsMap[key];
          switch (data[key]) {
            case this._visibility.hidden: {
              group.setSelection([group.getSelectables()[0]]);
              break;
            }
            case this._visibility.readOnly: {
              group.setSelection([group.getSelectables()[1]]);
              break;
            }
            case this._visibility.readWrite: {
              group.setSelection([group.getSelectables()[2]]);
              break;
            }
          }
        }
      }
    },

    linkAdded: function(portId, controlLink) {
      let data = this._getCtrlFieldChild(portId);
      if (data) {
        let child = data.child;
        let idx = data.idx;
        const layoutProps = child.getLayoutProperties();
        controlLink.oldCtrl = child;
        this._removeAt(idx);
        this._addAt(controlLink, idx, {
          row: layoutProps.row,
          column: this._gridPos.ctrlField
        });
      }
    },

    linkRemoved: function(portId) {
      let data = this._getCtrlFieldChild(portId);
      if (data) {
        let child = data.child;
        let idx = data.idx;
        const layoutProps = child.getLayoutProperties();
        this._removeAt(idx);
        this._addAt(child.oldCtrl, idx, {
          row: layoutProps.row,
          column: this._gridPos.ctrlField
        });
      }
    },

    __addAccessLevelRBs: function() {
      Object.keys(this._form.getControls()).forEach(portId => {
        this.__addAccessLevelRB(portId);
      });
    },

    __addAccessLevelRB: function(portId) {
      const rbHidden = new qx.ui.form.RadioButton(this.tr("Not Visible"));
      rbHidden.accessLevel = this._visibility.hidden;
      rbHidden.portId = portId;
      const rbReadOnly = new qx.ui.form.RadioButton(this.tr("Read Only"));
      rbReadOnly.accessLevel = this._visibility.readOnly;
      rbReadOnly.portId = portId;
      const rbEditable = new qx.ui.form.RadioButton(this.tr("Editable"));
      rbEditable.accessLevel = this._visibility.readWrite;
      rbEditable.portId = portId;

      const groupBox = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));
      groupBox.add(rbHidden);
      groupBox.add(rbReadOnly);
      groupBox.add(rbEditable);

      const group = new qx.ui.form.RadioGroup(rbHidden, rbReadOnly, rbEditable);
      group.setSelection([rbEditable]);
      this.__ctrlRBsMap[portId] = group;
      group.addListener("changeSelection", this.__onAccessLevelChanged, this);

      const ctrlField = this._getCtrlFieldChild(portId);
      if (ctrlField) {
        const idx = ctrlField.idx;
        const child = ctrlField.child;
        const layoutProps = child.getLayoutProperties();
        this._addAt(groupBox, idx, {
          row: layoutProps.row,
          column: this._gridPos.accessLevel
        });
      }
    },

    __onAccessLevelChanged: function(e) {
      const selectedButton = e.getData()[0];
      const {
        accessLevel,
        portId
      } = selectedButton;

      const data = {};
      data[portId] = accessLevel;

      this.__setAccessLevel(data);

      let inputAccess = this.getNode().getInputAccess();
      if (inputAccess === null) {
        inputAccess = {};
      }
      inputAccess[portId] = accessLevel;
      this.getNode().setInputAccess(inputAccess);

      const propWidget = this.getNode().getPropsWidget();
      propWidget.setAccessLevel(data);
    },

    __addDelTag: function(label) {
      const newLabel = "<del>" + label + "</del>";
      return newLabel;
    },

    __removeDelTag: function(label) {
      let newLabel = label.replace("<del>", "");
      newLabel = newLabel.replace("</del>", "");
      return newLabel;
    },

    __setAccessLevel: function(data) {
      for (const key in data) {
        const label = this._getLabelFieldChild(key).child;
        const control = this._form.getControl(key);
        switch (data[key]) {
          case this._visibility.hidden: {
            const newLabel = this.__addDelTag(label.getValue());
            label.setValue(newLabel);
            label.setEnabled(false);
            control.setEnabled(false);
            break;
          }
          case this._visibility.readOnly: {
            const newLabel = this.__removeDelTag(label.getValue());
            label.setValue(newLabel);
            label.setEnabled(false);
            control.setEnabled(false);
            break;
          }
          case this._visibility.readWrite: {
            const newLabel = this.__removeDelTag(label.getValue());
            label.setValue(newLabel);
            label.setEnabled(true);
            control.setEnabled(true);
            break;
          }
        }
      }
    },

    __getRadioButtonsFieldChild: function(portId) {
      return this._getLayoutChild(portId, this._gridPos.accessLevel);
    }
  }
});
