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

qx.Class.define("osparc.component.node.DataSourceNodeView", {
  extend: osparc.component.node.BaseNodeView,

  members: {
    __currentOutputs: null,

    // overridden
    isSettingsGroupShowable: function() {
      return false;
    },

    // overridden
    _addSettings: function() {
      return;
    },

    // overridden
    _addIFrame: function() {
      this.__buildMyLayout();
    },

    // overridden
    _openEditAccessLevel: function() {
      return;
    },

    // overridden
    _applyNode: function(node) {
      if (!node.isDataSource()) {
        console.error("Only file picker nodes are supported");
      }
      this.base(arguments, node);
    },

    __createTypeBox: function(selection) {
      const dataTypes = [
        "integer",
        "number",
        "boolean",
        "string",
        "data"
      ];

      const dataTypesBox = new qx.ui.form.SelectBox();
      dataTypes.forEach(dataType => {
        const dataTypeItem = new qx.ui.form.ListItem(qx.lang.String.firstUp(dataType));
        dataTypeItem.dataType = dataType;
        dataTypesBox.add(dataTypeItem);

        if (selection && selection.includes(dataTypeItem.dataType)) {
          dataTypesBox.setSelection([dataTypeItem]);
        }
      });
      return dataTypesBox;
    },

    __buildMyLayout: function() {
      const node = this.getNode();
      if (!node) {
        return;
      }

      const info = new qx.ui.basic.Label("Add the item to a list that will be iterated");
      this._mainView.add(info);

      const currentOutputs = this.__currentOutputs = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
      this._mainView.add(currentOutputs);
      this.__rebuildCurrentOutputs();

      const addNewBtn = new qx.ui.form.Button().set({
        allowGrowX: false,
        allowGrowY: false,
        label: this.tr("Add new"),
        icon: "@FontAwesome5Solid/plus/14"
      });
      addNewBtn.addListener("execute", () => {
        const metaData = node.getMetaData();
        osparc.data.model.DynamicOutputs.addOutput(metaData, "out_05", "integer", "integers");
        node.setOutputs(metaData["outputs"]);
        this.__rebuildCurrentOutputs();
      }, this);
      this._mainView.add(addNewBtn);
    },

    __rebuildCurrentOutputs: function() {
      const node = this.getNode();
      const currentOutputs = this.__currentOutputs;
      currentOutputs.removeAll();

      Object.values(node.getOutputs()).forEach(output => {
        const outputEntry = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));

        const key = output["keyId"];

        const label = new osparc.ui.form.EditLabel(output["label"]);
        label.addListener("editValue", e => {
          label.setValue(e.getData());
        }, this);
        outputEntry.add(label);

        const dataTypesBox = this.__createTypeBox(output["type"]);
        outputEntry.add(dataTypesBox);

        const listOfValues = new qx.ui.form.TextField();
        const value = node.getOutput(key)["value"];
        if (value) {
          listOfValues.setValue(value);
        }
        outputEntry.add(listOfValues, {
          flex: 1
        });

        const saveParamBtn = new qx.ui.form.Button().set({
          allowGrowX: false,
          allowGrowY: false,
          icon: "@FontAwesome5Solid/check/14"
        });
        saveParamBtn.addListener("execute", () => {
          const metaData = node.getMetaData();
          osparc.data.model.DynamicOutputs.setOutput(metaData, key, dataTypesBox.getSelection()[0].dataType, listOfValues.getValue(), label.getValue());
          node.setOutputs(metaData["outputs"]);
          this.__rebuildCurrentOutputs();
        }, this);
        outputEntry.add(saveParamBtn);

        const removeParamBtn = new qx.ui.form.Button().set({
          allowGrowX: false,
          allowGrowY: false,
          icon: "@FontAwesome5Solid/trash/14"
        });
        removeParamBtn.addListener("execute", () => {
          const metaData = node.getMetaData();
          osparc.data.model.DynamicOutputs.removeOutput(metaData, key);
          node.setOutputs(metaData["outputs"]);
          this.__rebuildCurrentOutputs();
        }, this);
        outputEntry.add(removeParamBtn);

        currentOutputs.add(outputEntry);
      });
    }
  }
});
