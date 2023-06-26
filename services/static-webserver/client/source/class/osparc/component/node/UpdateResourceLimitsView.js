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

qx.Class.define("osparc.component.node.UpdateResourceLimitsView", {
  extend: osparc.component.node.ServiceOptionsView,

  events: {
    "limitsChanged": "qx.event.type.Event"
  },

  members: {
    __resourceFields: null,
    __saveBtn: null,

    _applyNode: function(node) {
      if (node.isComputational() || node.isDynamic()) {
        if (node.isComputational()) {
          node.getStatus().bind("interactive", this, "enabled", {
            converter: () => !osparc.data.model.NodeStatus.isComputationalRunning(node)
          });
        } else if (node.isDynamic()) {
          node.getStatus().bind("interactive", this, "enabled", {
            converter: interactive => interactive === "idle"
          });
        }
        this.__populateLayout();
      }
    },

    __populateLayout: function() {
      this.__resourceFields = [];
      this._removeAll();

      this._add(new qx.ui.basic.Label(this.tr("Update Service Limits")).set({
        font: "text-14"
      }));

      const resourcesLayout = osparc.info.ServiceUtils.createResourcesInfo(false);
      resourcesLayout.exclude();
      this._add(resourcesLayout);

      const node = this.getNode();
      const params = {
        url: {
          studyId: node.getStudy().getUuid(),
          nodeId: node.getNodeId()
        }
      };
      osparc.data.Resources.get("nodesInStudyResources", params)
        .then(serviceResources => {
          resourcesLayout.show();
          const layout = resourcesLayout.getChildren()[0];
          let row = 1;
          Object.entries(serviceResources).forEach(([imageName, imageInfo]) => {
            layout.add(new qx.ui.basic.Label(imageName).set({
              font: "text-13"
            }), {
              row,
              column: 0
            });
            if ("resources" in imageInfo) {
              const resourcesInfo = imageInfo["resources"];
              Object.keys(resourcesInfo).forEach(resourceKey => {
                let column = 1;
                const resourceInfo = resourcesInfo[resourceKey];
                let label = resourceKey;
                if (resourceKey === "RAM") {
                  label += " (GB)";
                }
                layout.add(new qx.ui.basic.Label(label).set({
                  font: "text-13"
                }), {
                  row,
                  column
                });
                column++;
                Object.keys(osparc.info.ServiceUtils.RESOURCES_INFO).forEach(resourceInfoKey => {
                  if (resourceInfoKey in resourceInfo) {
                    let value = resourceInfo[resourceInfoKey];
                    if (resourceKey === "RAM") {
                      value = osparc.utils.Utils.bytesToGB(value);
                    }
                    const spinner = new qx.ui.form.Spinner(0, value, 200).set({
                      singleStep: 0.1
                    });
                    const nf = new qx.util.format.NumberFormat();
                    nf.setMinimumFractionDigits(1);
                    nf.setMaximumFractionDigits(1);
                    spinner.setNumberFormat(nf);

                    spinner.imageName = imageName;
                    spinner.resourceKey = resourceKey;
                    this.__resourceFields.push(spinner);
                    if (!(resourceKey === "VRAM")) {
                      layout.add(spinner, {
                        row,
                        column
                      });
                    }
                    column++;
                  }
                });
                row++;
              });
            }
          });

          const buttonsLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
          this._add(buttonsLayout);

          const resetBtn = new qx.ui.form.Button(this.tr("Reset"));
          resetBtn.addListener("execute", () => this.__populateLayout(), this);
          buttonsLayout.add(resetBtn);

          const saveBtn = this.__saveBtn = new osparc.ui.form.FetchButton(this.tr("Save")).set({
            center: true,
            appearance: "strong-button"
          });
          saveBtn.addListener("execute", () => this.__saveValues(serviceResources), this);
          buttonsLayout.add(saveBtn);
        })
        .catch(err => console.error(err));

      return resourcesLayout;
    },

    __saveValues: function(serviceResources) {
      this.__saveBtn.setFetching(true);
      const updatedResources = osparc.utils.Utils.deepCloneObject(serviceResources);
      this.__resourceFields.forEach(resourceField => {
        if (
          resourceField.imageName in updatedResources &&
          resourceField.resourceKey in updatedResources[resourceField.imageName].resources
        ) {
          let value = resourceField.getValue();
          if (resourceField.resourceKey === "RAM") {
            value = osparc.utils.Utils.gBToBytes(value);
          }
          updatedResources[resourceField.imageName].resources[resourceField.resourceKey]["limit"] = value;
        }
      });
      const node = this.getNode();
      const params = {
        url: {
          studyId: node.getStudy().getUuid(),
          nodeId: node.getNodeId()
        },
        data: updatedResources
      };
      osparc.data.Resources.fetch("nodesInStudyResources", "put", params)
        .then(() => {
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Limits successfully updated"));
          this.fireEvent("limitsChanged");
        })
        .catch(err => {
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Something went wrong Updating the limits"), "ERROR");
          console.error(err);
        })
        .finally(() => {
          this.__saveBtn.setFetching(false);
          this.__populateLayout();
        });
    }
  }
});
