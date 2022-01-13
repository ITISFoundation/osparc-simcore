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

/**
 * A special renderer for AutoForms which includes notes below the section header
 * widget and next to the individual form widgets.
 */


qx.Class.define("osparc.component.form.renderer.PropFormBase", {
  extend: qx.ui.form.renderer.Single,
  type: "abstract",

  /**
   * @param form {osparc.component.form.Auto} form widget to embed
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
    fl.setColumnFlex(this.self().gridPos.label, 0);
    fl.setColumnAlign(this.self().gridPos.label, "left", "top");
    fl.setColumnFlex(this.self().gridPos.info, 0);
    fl.setColumnAlign(this.self().gridPos.info, "left", "middle");
    fl.setColumnFlex(this.self().gridPos.ctrlField, 1);
    fl.setColumnMinWidth(this.self().gridPos.ctrlField, 50);
  },

  properties: {
    node: {
      check: "osparc.data.model.Node",
      nullable: true
    }
  },

  statics: {
    gridPos: {
      label: 0,
      info: 1,
      ctrlField: 2,
      unit: 3,
      fieldLinkUnlink: 4
    },

    getDisableables: function() {
      return [
        this.gridPos.label,
        this.gridPos.ctrlField
      ];
    }
  },

  // eslint-disable-next-line qx-rules/no-refs-in-members
  members: {
    _visibility: {
      hidden: "Invisible",
      readOnly: "ReadOnly",
      readWrite: "ReadAndWrite"
    },

    addItems: function(items, names, title, itemOptions, headerOptions) {
      // add the header
      if (title !== null) {
        this._add(
          this._createHeader(title), {
            row: this._row,
            column: this.self().gridPos.label,
            colSpan: Object.keys(this.self().gridPos).length
          }
        );
        this._row++;
      }

      // add the items
      for (let i = 0; i < items.length; i++) {
        const item = items[i];

        const label = this._createLabel(names[i], item);
        label.setBuddy(item);
        this._add(label, {
          row: this._row,
          column: this.self().gridPos.label
        });

        const info = this._createInfoWHint(item.description);
        this._add(info, {
          row: this._row,
          column: this.self().gridPos.info
        });

        this._add(item, {
          row: this._row,
          column: this.self().gridPos.ctrlField
        });

        const unit = this._createUnit(item.unitShort, item.unitLong);
        this._add(unit, {
          row: this._row,
          column: this.self().gridPos.unit
        });

        this._connectVisibility(item, label);
        // store the names for translation
        if (qx.core.Environment.get("qx.dynlocale")) {
          this._names.push({
            name: names[i],
            label: label,
            item: items[i]
          });
        }

        this._row++;
      }
    },

    getValues: function() {
      let data = this._form.getData();
      for (const portId in data) {
        let ctrl = this._form.getControl(portId);
        if (ctrl && ctrl["link"]) {
          data[portId] = ctrl["link"];
        }
        if (ctrl && ctrl["parameter"]) {
          data[portId] = "{{" + ctrl["parameter"].id + "}}";
        }
        // FIXME: "null" should be a valid input
        if (data[portId] === "null") {
          data[portId] = null;
        }
      }
      let filteredData = {};
      for (const key in data) {
        if (data[key] !== null) {
          filteredData[key] = data[key];
        }
      }
      return filteredData;
    },

    hasVisibleInputs: function() {
      const children = this._getChildren();
      for (let i=0; i<children.length; i++) {
        const child = children[i];
        const layoutProps = child.getLayoutProperties();
        if (layoutProps.column === this.self().gridPos.label && child.getBuddy().isVisible()) {
          return true;
        }
      }
      return false;
    },

    hasAnyPortConnected: function() {
      const data = this._form.getData();
      for (const portId in data) {
        const ctrl = this._form.getControl(portId);
        if (ctrl && ctrl["link"]) {
          return true;
        }
      }
      return false;
    },

    /**
      * @abstract
      */
    setAccessLevel: function() {
      throw new Error("Abstract method called!");
    },

    _createInfoWHint: function(hint) {
      const infoWHint = new osparc.ui.hint.InfoHint(hint);
      return infoWHint;
    },

    _createUnit: function(unitShort, unitLong) {
      const unitLabel = this.__unitLabel = new qx.ui.basic.Label().set({
        alignY: "bottom",
        paddingBottom: 1,
        value: unitShort || null,
        toolTipText: unitLong || null,
        visibility: unitShort ? "visible" : "excluded"
      });
      return unitLabel;
    },

    _getLayoutChild: function(portId, column) {
      let row = null;
      const children = this._getChildren();
      for (let i=0; i<children.length; i++) {
        const child = children[i];
        const layoutProps = child.getLayoutProperties();
        if (layoutProps.column === this.self().gridPos.label &&
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

    _getLabelFieldChild: function(portId) {
      return this._getLayoutChild(portId, this.self().gridPos.label);
    },

    _getCtrlFieldChild: function(portId) {
      return this._getLayoutChild(portId, this.self().gridPos.ctrlField);
    }
  }
});
