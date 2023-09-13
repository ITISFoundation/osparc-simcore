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


qx.Class.define("osparc.form.renderer.PropFormBase", {
  extend: qx.ui.form.renderer.Single,
  type: "abstract",

  /**
   * @param form {osparc.form.Auto} form widget to embed
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
    fl.setSpacingY(0); // so that the "excluded" rows do not take any space
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

    ROW_HEIGHT: 28,

    getDisableables: function() {
      return [
        this.GRID_POS.LABEL,
        this.GRID_POS.CTRL_FIELD
      ];
    },

    updateUnitLabelPrefix: function(item) {
      const {
        unitShort,
        unitLong
      } = osparc.utils.Units.getLabels(item.unit, item.unitPrefix);
      if ("unitLabel" in item) {
        const unitLabel = item["unitLabel"];
        unitLabel.set({
          value: unitShort || null,
          toolTipText: unitLong || null,
          visibility: unitShort ? "visible" : "excluded"
        });
      }
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
        // compensate the SpacingY: 0
        label.set({
          marginTop: 3
        });
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

        // compensate the SpacingY: 0
        this._getLayout().setRowHeight(this._row, this.self().ROW_HEIGHT);

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
      // convert values to service specified units
      const changedXUnits = this.getChangedXUnits();
      Object.keys(changedXUnits).forEach(portId => {
        const ctrl = this._form.getControl(portId);
        const nodeMD = this.getNode().getMetaData();
        const {
          unitPrefix
        } = osparc.utils.Units.decomposeXUnit(nodeMD.inputs[portId]["x_unit"]);
        filteredData[portId] = osparc.utils.Units.convertValue(filteredData[portId], ctrl.unitPrefix, unitPrefix);
      });
      return filteredData;
    },

    getChangedXUnits: function() {
      const xUnits = {};
      const ctrls = this._form.getControls();
      for (const portId in ctrls) {
        const ctrl = this._form.getControl(portId);
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

    setInputsUnits: function(inputsUnits) {
      Object.keys(inputsUnits).forEach(portId => {
        const item = this._form.getControl(portId);
        this.__switchPrefix(item, item.unitPrefix, osparc.utils.Units.decomposeXUnit(inputsUnits[portId]).unitPrefix);
      });
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
      const infoWHint = new osparc.form.PortInfoHint(hint);
      return infoWHint;
    },

    __createUnit: function(item) {
      let {
        unit,
        unitPrefix,
        unitShort,
        unitLong
      } = item;
      let unitRegistered = false;
      if (unit) {
        const labels = osparc.utils.Units.getLabels(unit, unitPrefix);
        if (labels !== null) {
          unitShort = labels.unitShort;
          unitLong = labels.unitLong;
          unitRegistered = true;
        }
      }
      const unitLabel = new qx.ui.basic.Label().set({
        rich: true,
        alignY: "bottom",
        paddingBottom: 1,
        value: unitShort || null,
        toolTipText: unitLong || null,
        visibility: unitShort ? "visible" : "excluded"
      });
      if (unit && unitRegistered) {
        unitLabel.addListener("pointerover", () => unitLabel.setCursor("pointer"), this);
        unitLabel.addListener("pointerout", () => unitLabel.resetCursor(), this);
        const nodeMD = this.getNode().getMetaData();
        const originalUnit = "x_unit" in nodeMD.inputs[item.key] ? osparc.utils.Units.decomposeXUnit(nodeMD.inputs[item.key]["x_unit"]) : null;
        unitLabel.addListener("tap", () => {
          const nextPrefix = osparc.utils.Units.getNextPrefix(item.unitPrefix, originalUnit.unitPrefix);
          this.__switchPrefix(item, item.unitPrefix, nextPrefix.long);
        }, this);
      }
      item.unitLabel = unitLabel;
      return unitLabel;
    },

    __switchPrefix: function(item, oldPrefix, newPrefix) {
      let newValue = osparc.utils.Units.convertValue(item.getValue(), oldPrefix, newPrefix);
      item.unitPrefix = newPrefix;
      if ("type" in item && item.type !== "integer") {
        newValue = String(newValue);
      }
      item.setValue(newValue);
      this.self().updateUnitLabelPrefix(item);
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

    _getInfoFieldChild: function(portId) {
      return this._getLayoutChild(portId, this.self().GRID_POS.INFO);
    },

    _getCtrlFieldChild: function(portId) {
      return this._getLayoutChild(portId, this.self().GRID_POS.CTRL_FIELD);
    },

    __geUnitFieldChild: function(portId) {
      return this._getLayoutChild(portId, this.self().GRID_POS.UNIT);
    }
  }
});
