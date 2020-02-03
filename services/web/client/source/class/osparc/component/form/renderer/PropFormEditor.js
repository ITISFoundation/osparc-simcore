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
  extend: qx.ui.form.renderer.Single,

  /**
   * create a page for the View Tab with the given title
   *
   * @param form {osparc.component.form.Auto} form widget to embedd
   * @param node {osparc.data.model.Node} Node owning the widget
   */
  construct: function(form, node) {
    if (node) {
      this.setNode(node);
    } else {
      this.setNode(null);
    }

    this.base(arguments, form);

    const fl = this._getLayout();
    fl.setColumnFlex(0, 0);
    fl.setColumnAlign(0, "left", "top");
    fl.setColumnFlex(1, 1);
    fl.setColumnMinWidth(1, 130);
    fl.setColumnFlex(2, 0);

    this.__ctrlRBsMap = {};
    this.__addAccessLevelRBs();
  },

  events: {
    "dataFieldModified": "qx.event.type.Data"
  },

  properties: {
    node: {
      check: "osparc.data.model.Node",
      nullable: true
    }
  },

  // eslint-disable-next-line qx-rules/no-refs-in-members
  members: {
    _gridPos: {
      label: 0,
      entryField: 1,
      accessLevel: 2
    },
    _accessLevel: {
      hidden: 0,
      readOnly: 1,
      readAndWrite: 2
    },

    __ctrlRBsMap: null,

    addItems: function(items, names, title, itemOptions, headerOptions) {
      // add the header
      if (title !== null) {
        this._add(
          this._createHeader(title), {
            row: this._row,
            column: this._gridPos.label,
            colSpan: Object.keys(this._gridPos).length
          }
        );
        this._row++;
      }

      // add the items
      for (let i = 0; i < items.length; i++) {
        let item = items[i];
        let label = this._createLabel(names[i], item);
        this._add(label, {
          row: this._row,
          column: this._gridPos.label
        });
        label.setBuddy(item);

        const field = new osparc.component.form.FieldWHint(null, item.description, item);
        field.key = item.key;
        this._add(field, {
          row: this._row,
          column: this._gridPos.entryField
        });
        this._row++;
        this._connectVisibility(item, label);
        // store the names for translation
        if (qx.core.Environment.get("qx.dynlocale")) {
          this._names.push({
            name: names[i],
            label: label,
            item: items[i]
          });
        }
      }
    },

    setAccessLevel: function(data) {
      for (const key in data) {
        const control = this.__getRadioButtonsFieldChild(key);
        if (control) {
          const group = this.__ctrlRBsMap[key];
          switch (data[key]) {
            case "Invisible": {
              group.setSelection([group.getSelectables()[0]]);
              break;
            }
            case "ReadOnly": {
              group.setSelection([group.getSelectables()[1]]);
              break;
            }
            case "ReadAndWrite": {
              group.setSelection([group.getSelectables()[2]]);
              break;
            }
          }
        }
      }
    },

    __addAccessLevelRBs: function() {
      const ctrls = this._form.getControls();
      for (const portId in ctrls) {
        const rbHidden = new qx.ui.form.RadioButton(this.tr("Not Visible"));
        rbHidden.accessLevel = "Invisible";
        rbHidden.portId = portId;
        const rbReadOnly = new qx.ui.form.RadioButton(this.tr("Read Only"));
        rbReadOnly.accessLevel = "ReadOnly";
        rbReadOnly.portId = portId;
        const rbEditable = new qx.ui.form.RadioButton(this.tr("Editable"));
        rbEditable.accessLevel = "ReadAndWrite";
        rbEditable.portId = portId;

        const groupBox = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));
        groupBox.add(rbHidden);
        groupBox.add(rbReadOnly);
        groupBox.add(rbEditable);

        const group = new qx.ui.form.RadioGroup(rbHidden, rbReadOnly, rbEditable);
        group.setSelection([rbEditable]);
        this.__ctrlRBsMap[portId] = group;
        group.addListener("changeSelection", this.__onAccessLevelChanged, this);

        const entryField = this.__getEntryFieldChild(portId);
        if (entryField) {
          const idx = entryField.idx;
          const child = entryField.child;
          const layoutProps = child.getLayoutProperties();
          this._addAt(groupBox, idx, {
            row: layoutProps.row,
            column: this._gridPos.accessLevel
          });
        }
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

      const inputAccess = this.getNode().getInputAccess();
      inputAccess[portId] = accessLevel;
      this.getNode().setInputAccess(inputAccess);

      const propWidget = this.getNode().getPropsWidget();
      propWidget.setAccessLevel(data);
    },

    addDelTag: function(label) {
      const newLabel = "<del>" + label + "</del>";
      return newLabel;
    },

    removeDelTag: function(label) {
      let newLabel = label.replace("<del>", "");
      newLabel = newLabel.replace("</del>", "");
      return newLabel;
    },

    __setAccessLevel: function(data) {
      for (const key in data) {
        const label = this.__getLabelFieldChild(key).child;
        const control = this._form.getControl(key);
        switch (data[key]) {
          case "Invisible": {
            const newLabel = this.addDelTag(label.getValue());
            label.setValue(newLabel);
            label.setEnabled(false);
            control.setEnabled(false);
            break;
          }
          case "ReadOnly": {
            const newLabel = this.removeDelTag(label.getValue());
            label.setValue(newLabel);
            label.setEnabled(false);
            control.setEnabled(false);
            break;
          }
          case "ReadAndWrite": {
            const newLabel = this.removeDelTag(label.getValue());
            label.setValue(newLabel);
            label.setEnabled(true);
            control.setEnabled(true);
            break;
          }
        }
      }
    },

    __getLayoutChild: function(portId, column) {
      let row = null;
      const children = this._getChildren();
      for (let i=0; i<children.length; i++) {
        const child = children[i];
        const layoutProps = child.getLayoutProperties();
        if (layoutProps.column === this._gridPos.label &&
          child.getBuddy().key === portId) {
          row = layoutProps.row;
          break;
        }
      }
      if (row !== null) {
        for (let i=0; i<children.length; i++) {
          const child = children[i];
          const layoutProps = child.getLayoutProperties();
          if (layoutProps.column === column &&
            layoutProps.row === row) {
            return {
              child,
              idx: i
            };
          }
        }
      }
      return null;
    },

    __getLabelFieldChild: function(portId) {
      return this.__getLayoutChild(portId, this._gridPos.label);
    },

    __getEntryFieldChild: function(portId) {
      return this.__getLayoutChild(portId, this._gridPos.entryField);
    },

    __getRadioButtonsFieldChild: function(portId) {
      return this.__getLayoutChild(portId, this._gridPos.accessLevel);
    }
  }
});
