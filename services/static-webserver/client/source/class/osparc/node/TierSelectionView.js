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

qx.Class.define("osparc.node.TierSelectionView", {
  extend: osparc.node.ServiceOptionsView,

  events: {
    "tierChanged": "qx.event.type.Event"
  },

  members: {
    _applyNode: function(node) {
      this.__populateLayout();

      this.base(arguments, node);
    },

    __populateLayout: function() {
      this._removeAll();

      this._add(new qx.ui.basic.Label(this.tr("Tiers")).set({
        font: "text-14"
      }));

      const tiersLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
      this._add(tiersLayout);

      const tierBox = new qx.ui.form.SelectBox().set({
        allowGrowX: false,
        allowGrowY: false
      });
      tiersLayout.add(tierBox);

      const node = this.getNode();
      osparc.store.Services.getPricingPlan(node.getKey(), node.getVersion())
        .then(pricingPlans => {
          if (pricingPlans && "pricingUnits" in pricingPlans && pricingPlans["pricingUnits"].length) {
            const pricingUnits = pricingPlans["pricingUnits"].map(pricingUnitData => {
              const pricingUnit = new osparc.data.model.PricingUnit(pricingUnitData);
              return pricingUnit;
            });
            pricingUnits.forEach(pricingUnit => {
              const tItem = new qx.ui.form.ListItem(pricingUnit.getName(), null, pricingUnit.getPricingUnitId());
              tierBox.add(tItem);
            });
            const studyId = node.getStudy().getUuid();
            const nodeId = node.getNodeId();
            osparc.store.Study.getSelectedPricingUnit(studyId, nodeId)
              .then(selectedPricingUnit => {
                if (selectedPricingUnit && selectedPricingUnit["pricingUnitId"]) {
                  const tierFound = tierBox.getSelectables().find(t => t.getModel() === selectedPricingUnit["pricingUnitId"]);
                  if (tierFound) {
                    tierBox.setSelection([tierFound]);
                  } else {
                    console.error("Tier not found");
                  }
                }
              })
              .finally(() => {
                const pUnitUIs = [];
                pricingUnits.forEach(pricingUnit => {
                  const pUnitUI = new osparc.study.PricingUnitTier(pricingUnit).set({
                    showEditButton: false,
                  });
                  pUnitUI.getChildControl("name").exclude();
                  pUnitUI.exclude();
                  tiersLayout.add(pUnitUI);
                  pUnitUIs.push(pUnitUI);
                });
                const showSelectedTier = pricingUnitId => {
                  pUnitUIs.forEach(pUnitUI => pUnitUI.exclude());
                  if (pricingUnitId) {
                    const pUnitFound = pUnitUIs.find(pUnitUI => pUnitUI.getUnitData().getPricingUnitId() === pricingUnitId)
                    if (pUnitFound) {
                      pUnitFound.show();
                    }
                  }
                }
                showSelectedTier(tierBox.getSelection() && tierBox.getSelection()[0].getModel());
                tierBox.addListener("changeSelection", e => {
                  const selection = e.getData();
                  if (selection.length) {
                    tierBox.setEnabled(false);
                    const selectedUnitId = selection[0].getModel();
                    osparc.store.Study.updateSelectedPricingUnit(studyId, nodeId, pricingPlans["pricingPlanId"], selectedUnitId)
                      .finally(() => {
                        tierBox.setEnabled(true);
                        showSelectedTier(selectedUnitId);
                      });
                  }
                }, this);
              });
          }
        });
    }
  }
});
