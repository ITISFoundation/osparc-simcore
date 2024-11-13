/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.node.LifeCycleView", {
  extend: osparc.node.ServiceOptionsView,

  members: {
    _applyNode: function(node) {
      if (node.isUpdatable() || node.isDeprecated() || node.isRetired()) {
        this.__populateLayout();
      }

      this.base(arguments, node);
    },

    __populateLayout: function() {
      this._removeAll();

      this.__addTitle();
      this.__addChip();
      this.__addDeprecationDate();

      if (this.getNode().isUpdatable()) {
        this.__addAutoUpdatableSection();
      } else {
        this.__addNonAutoUpdatableSection();
      }
    },

    __addTitle: function() {
      this._add(new qx.ui.basic.Label(this.tr("Update Service")).set({
        font: "text-14"
      }));
    },

    __addChip: function() {
      const node = this.getNode();

      let chip = null;
      if (node.isRetired()) {
        chip = osparc.service.StatusUI.createServiceRetiredChip();
      } else if (node.isDeprecated()) {
        chip = osparc.service.StatusUI.createServiceDeprecatedChip();
      }
      if (chip) {
        this._add(chip);
      }
    },

    __addDeprecationDate: function() {
      const node = this.getNode();

      if (node.isDeprecated()) {
        const deprecateDateLabel = new qx.ui.basic.Label(osparc.service.Utils.getDeprecationDateText(node.getMetaData())).set({
          rich: true
        });
        this._add(deprecateDateLabel);
      }
    },

    __addAutoUpdatableSection: function() {
      this.__addAutoUpdatableInstructions();
      this.__addAutoUpdateButtonsSection();
    },

    __addAutoUpdatableInstructions: function() {
      const node = this.getNode();

      let instructionsMsg = null;
      if (node.isRetired()) {
        instructionsMsg = osparc.service.Utils.RETIRED_AUTOUPDATABLE_INSTRUCTIONS;
      } else if (node.isUpdatable() || node.isDeprecated()) {
        instructionsMsg = osparc.service.Utils.DEPRECATED_AUTOUPDATABLE_INSTRUCTIONS;
      }
      if (instructionsMsg) {
        const instructionsLabel = new qx.ui.basic.Label(instructionsMsg).set({
          rich: true
        });
        this._add(instructionsLabel);
      }
    },

    __addAutoUpdateButtonsSection: function() {
      const node = this.getNode();

      const buttonsLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));

      const updateButton = new osparc.ui.form.FetchButton().set({
        label: this.tr("Update"),
        icon: "@MaterialIcons/update/14",
        backgroundColor: "strong-main"
      });
      const isUpdatable = this.getNode().isUpdatable();
      node.getStatus().bind("interactive", updateButton, "enabled", {
        converter: state => ["idle", "failed", "deprecated", "retired"].includes(state) && isUpdatable
      });
      updateButton.addListener("execute", () => {
        updateButton.setFetching(true);
        const latestCompatible = osparc.service.Utils.getLatestCompatible(node.getKey(), node.getVersion());
        if (node.getKey() !== latestCompatible["key"]) {
          node.setKey(latestCompatible["key"]);
        }
        if (node.getVersion() !== latestCompatible["version"]) {
          node.setVersion(latestCompatible["version"]);
        }
        node.fireEvent("updateStudyDocument");
        setTimeout(() => {
          updateButton.setFetching(false);
          node.requestStartNode();
        }, osparc.desktop.StudyEditor.AUTO_SAVE_INTERVAL);
      });

      buttonsLayout.add(updateButton);

      this._add(buttonsLayout);
    },

    __addNonAutoUpdatableSection: function() {
      const node = this.getNode();

      let instructionsMsg = null;
      if (node.isRetired()) {
        instructionsMsg = osparc.service.Utils.RETIRED_DYNAMIC_INSTRUCTIONS;
      } else if (node.isUpdatable() || node.isDeprecated()) {
        instructionsMsg = osparc.service.Utils.DEPRECATED_DYNAMIC_INSTRUCTIONS;
      }
      if (instructionsMsg) {
        const instructionsLabel = new qx.ui.basic.Label(instructionsMsg).set({
          rich: true
        });
        this._add(instructionsLabel);
      }
    }
  }
});
