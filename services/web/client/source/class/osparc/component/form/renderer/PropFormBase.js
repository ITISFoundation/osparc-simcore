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
    fl.setColumnFlex(this.self().GRID_POS.LABEL, 0);
    fl.setColumnAlign(this.self().GRID_POS.LABEL, "left", "top");
    fl.setColumnFlex(this.self().GRID_POS.INFO, 0);
    fl.setColumnAlign(this.self().GRID_POS.INFO, "left", "middle");
    fl.setColumnFlex(this.self().GRID_POS.CTRL_FIELD, 1);
    fl.setColumnMinWidth(this.self().GRID_POS.CTRL_FIELD, 50);
  },

  properties: {
    node: {
      check: "osparc.data.model.Node",
      nullable: true
    }
  },

  statics: {
    GRID_POS: {
      LABEL: 0,
      INFO: 1,
      CTRL_FIELD: 2,
      UNIT: 3,
      FIELD_LINK_UNLINK: 4
    },

    getDisableables: function() {
      return [
        this.GRID_POS.LABEL,
        this.GRID_POS.CTRL_FIELD
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
            column: this.self().GRID_POS.LABEL,
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
          column: this.self().GRID_POS.LABEL
        });

        const info = this._createInfoWHint(item.description);
        this._add(info, {
          row: this._row,
          column: this.self().GRID_POS.INFO
        });

        this._add(item, {
          row: this._row,
          column: this.self().GRID_POS.CTRL_FIELD
        });

        const unit = this.__createUnit(item);
        this._add(unit, {
          row: this._row,
          column: this.self().GRID_POS.UNIT
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

    getChangedUnits: function() {
      const xUnits = {};
      const ctrls = this._form.getControls();
      for (const portId in ctrls) {
        let ctrl = this._form.getControl(portId);
        xUnits[portId] = osparc.utils.Units.composeXUnit(ctrl.unit, ctrl.unitPrefix);
      }
      const nodeMD = this.getNode().getMetaData();
      const changedXUnits = {};
      for (const portId in xUnits) {
        if (xUnits[portId] === null) {
          break;
        }
        if (!("x_unit" in nodeMD.inputs[portId])) {
          break;
        }
        if (xUnits[portId] !== nodeMD.inputs[portId].x_unit) {
          changedXUnits[portId] = xUnits[portId];
        }
      }
      return changedXUnits;
    },

    hasVisibleInputs: function() {
      const children = this._getChildren();
      for (let i=0; i<children.length; i++) {
        const child = children[i];
        const layoutProps = child.getLayoutProperties();
        if (layoutProps.column === this.self().GRID_POS.LABEL && child.getBuddy().isVisible()) {
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

    __createUnit: function(item) {
      let {
        unit,
        unitPrefix,
        unitShort,
        unitLong
      } = item;
      if (unit) {
        unitShort = osparc.utils.Units.getShortLabel(unit, unitPrefix);
        unitLong = osparc.utils.Units.getLongLabel(unit, unitPrefix);
      }
      const unitLabel = this.__unitLabel = new qx.ui.basic.Label().set({
        alignY: "bottom",
        paddingBottom: 1
      });
      const renderUnit = (unitS, unitL) => {
        unitLabel.set({
          value: unitS || null,
          toolTipText: unitL || null,
          visibility: unitShort ? "visible" : "excluded"
        });
      };
      renderUnit(unitShort, unitLong);
      if (unit) {
        unitLabel.addListener("pointerover", () => unitLabel.setCursor("pointer"), this);
        unitLabel.addListener("pointerout", () => unitLabel.resetCursor(), this);
        unitLabel.addListener("tap", () => {
          const nextPrefix = osparc.utils.Units.getNextPrefix(item.unitPrefix);
          this._switchPrefix(item, item.unitPrefix, nextPrefix.long);
          item.unitPrefix = nextPrefix.long;
          unitShort = osparc.utils.Units.getShortLabel(unit, item.unitPrefix);
          unitLong = osparc.utils.Units.getLongLabel(unit, item.unitPrefix);
          renderUnit(unitShort, unitLong);
        }, this);
      }
      return unitLabel;
    },

    _switchPrefix: function(item, oldPrefix, newPrefix) {
      const oldMulitplier = osparc.utils.Units.getPrefixMultiplier(oldPrefix);
      const newMulitplier = osparc.utils.Units.getPrefixMultiplier(newPrefix);
      const multiplier = oldMulitplier/newMulitplier;
      item.setValue(String(item.getValue()*multiplier));
    },

    _getLayoutChild: function(portId, column) {
      let row = null;
      const children = this._getChildren();
      for (let i=0; i<children.length; i++) {
        const child = children[i];
        const layoutProps = child.getLayoutProperties();
        if (layoutProps.column === this.self().GRID_POS.LABEL &&
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
      return this._getLayoutChild(portId, this.self().GRID_POS.LABEL);
    },

    _getCtrlFieldChild: function(portId) {
      return this._getLayoutChild(portId, this.self().GRID_POS.CTRL_FIELD);
    }
  }
});
