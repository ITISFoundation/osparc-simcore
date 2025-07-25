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

    // override qx.ui.form.renderer.Single's grid layout
    const grid = this.getLayout();
    grid.setSpacingY(0); // so that the "excluded" rows do not take any space
    grid.setColumnFlex(this.self().GRID_POS.LABEL, 1);
    grid.setColumnFlex(this.self().GRID_POS.INFO, 0);
    grid.setColumnFlex(this.self().GRID_POS.CTRL_FIELD, 1);
    grid.setColumnFlex(this.self().GRID_POS.UNIT, 0);
    grid.setColumnFlex(this.self().GRID_POS.FIELD_LINK_UNLINK, 0);
    grid.setColumnMinWidth(this.self().GRID_POS.CTRL_FIELD, 50);
    Object.keys(this.self().GRID_POS).forEach((_, idx) => grid.setColumnAlign(idx, "left", "middle"));
  },

  properties: {
    node: {
      check: "osparc.data.model.Node",
      nullable: true
    }
  },

  events: {
    "unitChanged": "qx.event.type.Data"
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

    /**
     * override
     *
     * @param items {qx.ui.core.Widget[]} An array of form items to render.
     * @param names {String[]} An array of names for the form items.
     * @param title {String?} A title of the group you are adding.
     */
    addItems: function(items, names, title) {
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
      let firstLabel = null;
      for (let i = 0; i < items.length; i++) {
        const item = items[i];

        const label = this._createLabel(names[i], item);
        if (firstLabel === null) {
          firstLabel = label;
        }
        label.set({
          // override ``rich``: to false, it is required for showing the cut off ellipsis.
          // rich: false,
          toolTipText: names[i]
        });
        // leave ``rich`` set to true. Ellipsis will be handled here:
        label.getContentElement().setStyles({
          "text-overflow": "ellipsis",
          "white-space": "nowrap"
        });
        label.setBuddy(item);
        this._add(label, {
          row: this._row,
          column: this.self().GRID_POS.LABEL
        });

        const info = this.__createInfoWHint(item.description);
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

        this._row++;

        this._connectVisibility(item, label);
      }

      this.addListener("appear", () => this.__makeLabelsResponsive(), this);
      this.addListener("resize", () => this.__makeLabelsResponsive(), this);
    },

    __makeLabelsResponsive: function() {
      const grid = this.getLayout()
      const firstColumnWidth = osparc.utils.Utils.getGridsFirstColumnWidth(grid);
      if (firstColumnWidth === null) {
        // not rendered yet
        setTimeout(() => this.__makeLabelsResponsive(), 100);
        return;
      }
      const extendedVersion = firstColumnWidth > 300;

      const inputs = this.getNode().getInputs();
      Object.keys(inputs).forEach((portId, idx) => {
        if (inputs[portId].description) {
          this._getLabelFieldChild(portId).child.set({
            value: extendedVersion ? inputs[portId].label + ". " + inputs[portId].description + ":" : inputs[portId].label,
            toolTipText: extendedVersion ? inputs[portId].label + "<br>" + inputs[portId].description : inputs[portId].label
          });

          if (grid.getRowHeight(idx) === 0) {
            // the port might be hidden
            this._getInfoFieldChild(portId).child.setVisibility("hidden");
          } else {
            this._getInfoFieldChild(portId).child.setVisibility(extendedVersion ? "hidden" : "visible");
          }

          grid.setColumnMinWidth(this.self().GRID_POS.CTRL_FIELD, extendedVersion ? 150 : 50);
        }
      });
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

    evalFieldRequired: function(portId) {
      const label = this._getLabelFieldChild(portId).child;
      const inputsRequired = this.getNode().getInputsRequired();

      // add star (*) to the label
      const requiredSuffix = " *";
      let newLabel = label.getValue();
      newLabel = newLabel.replace(requiredSuffix, "");
      if (inputsRequired.includes(portId)) {
        newLabel += requiredSuffix;
      }
      label.setValue(newLabel);

      // add "required" text to the label's tooltip
      const toolTipSuffix = "<br>" + this.tr("Required input: without it, the service will not start/run.");
      let newToolTip = label.getToolTipText();
      newToolTip = newToolTip.replace(toolTipSuffix, "");
      if (inputsRequired.includes(portId)) {
        newToolTip += toolTipSuffix;
      }
      label.setToolTipText(newToolTip);

      // add "required" text to the description
      const infoButton = this._getInfoFieldChild(portId).child;
      let newHintText = infoButton.getHintText();
      newHintText = newHintText.replace(toolTipSuffix, "");
      if (inputsRequired.includes(portId)) {
        newHintText += toolTipSuffix;
      }
      infoButton.setHintText(newHintText);
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

    __createInfoWHint: function(hint) {
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
      this.fireDataEvent("unitChanged", {
        portId: item.key,
        prefix: newPrefix,
      });
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
