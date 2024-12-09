/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2024 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.store.Pricing", {
  extend: qx.core.Object,
  type: "singleton",

  construct: function() {
    this.base(arguments);

    this.pricingPlansCached = [];
  },

  events: {
    "pricingPlansChanged": "qx.event.type.Data",
  },

  members: {
    pricingPlansCached: null,

    fetchPricingPlans: function() {
      return osparc.data.Resources.fetch("pricingPlans", "get")
        .then(pricingPlansData => {
          const pricingPlans = [];
          pricingPlansData.forEach(pricingPlanData => {
            const pricingPlan = this.__addToCache(pricingPlanData);
            pricingPlans.push(pricingPlan);
          });
          return pricingPlans;
        });
    },

    postPricingPlan: function(newPricingPlanData) {
      const params = {
        data: newPricingPlanData
      };
      return osparc.data.Resources.fetch("pricingPlans", "post", params)
        .then(pricingPlanData => {
          const pricingPlan = this.__addToCache(pricingPlanData);
          this.fireDataEvent("pricingPlansChanged", pricingPlan);
          return pricingPlan;
        });
    },

    putPricingPlan: function(pricingPlanId, updateData) {
      const params = {
        url: {
          pricingPlanId
        },
        data: updateData
      };
      return osparc.data.Resources.getInstance().fetch("pricingPlans", "update", params)
        .then(pricingPlanData => {
          return this.__addToCache(pricingPlanData);
        })
        .catch(console.error);
    },

    fetchPricingUnits: function(pricingPlanId) {
      const params = {
        url: {
          pricingPlanId,
        }
      };
      return osparc.data.Resources.fetch("pricingPlans", "getOne", params)
        .then(pricingPlanData => {
          const pricingPlan = this.__addToCache(pricingPlanData);
          const pricingUnits = pricingPlan.getPricingUnits();
          pricingUnits.forEach(pricingUnit => {
            pricingPlan.bind("classification", pricingUnit, "classification");
          })
          return pricingUnits;
        });
    },

    getPricingPlans: function() {
      return this.pricingPlansCached;
    },

    getPricingPlan: function(pricingPlanId = null) {
      return this.pricingPlansCached.find(f => f.getPricingPlanId() === pricingPlanId);
    },

    __addToCache: function(pricingPlanData) {
      let pricingPlan = this.pricingPlansCached.find(f => f.getPricingPlanId() === pricingPlanData["pricingPlanId"]);
      if (pricingPlan) {
        // put
        pricingPlan.set({
          pricingPlanKey: pricingPlanData["pricingPlanKey"],
          name: pricingPlanData["displayName"],
          description: pricingPlanData["description"],
          classification: pricingPlanData["classification"],
          isActive: pricingPlanData["isActive"],
        });
      } else {
        // get and post
        pricingPlan = new osparc.data.model.PricingPlan(pricingPlanData);
        this.pricingPlansCached.unshift(pricingPlan);
      }
      return pricingPlan;
    },

    __addPricingUnitToCache: function(pricingPlan, pricingUnitData) {
      const pricingUnits = pricingPlan.getPricingUnits();
      let pricingUnit = pricingUnits ? pricingUnits.find(unit => ("getPricingUnitId" in unit) && unit.getPricingUnitId() === pricingUnitData["pricingUnitId"]) : null;
      if (pricingUnit) {
        const props = Object.keys(qx.util.PropertyUtil.getProperties(osparc.data.model.PricingPlan));
        // put
        Object.keys(pricingUnitData).forEach(key => {
          if (props.includes(key)) {
            pricingPlan.set(key, pricingUnitData[key]);
          }
        });
      } else {
        // get and post
        pricingUnit = new osparc.data.model.PricingUnit(pricingUnitData);
        pricingPlan.bind("classification", pricingUnit, "classification");
        pricingUnits.push(pricingUnit);
      }
      return pricingUnit;
    },
  }
});
