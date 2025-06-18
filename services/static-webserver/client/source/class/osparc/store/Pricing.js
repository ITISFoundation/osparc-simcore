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

    this.__pricingPlansCached = [];
  },

  members: {
    __pricingPlansCached: null,

    fetchPricingPlans: function() {
      const resourceName = osparc.data.Permissions.getInstance().isAdmin() ? "adminPricingPlans" : "pricingPlans";
      return osparc.data.Resources.getInstance().getAllPages(resourceName)
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
      return osparc.data.Resources.fetch("adminPricingPlans", "post", params)
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
      return osparc.data.Resources.getInstance().fetch("adminPricingPlans", "update", params)
        .then(pricingPlanData => {
          return this.__addToCache(pricingPlanData);
        })
        .catch(console.error);
    },

    fetchPricingUnits: function(pricingPlanId) {
      if (this.getPricingPlan(pricingPlanId) && this.getPricingPlan(pricingPlanId).getPricingUnits().length !== 0) {
        return new Promise(resolve => resolve(this.getPricingPlan(pricingPlanId).getPricingUnits()));
      }
      const params = {
        url: {
          pricingPlanId,
        }
      };
      const resourceName = osparc.data.Permissions.getInstance().isAdmin() ? "adminPricingPlans" : "pricingPlans";
      return osparc.data.Resources.fetch(resourceName, "getOne", params)
        .then(pricingPlanData => {
          const pricingPlan = this.__addToCache(pricingPlanData);
          const pricingUnits = pricingPlan.getPricingUnits();
          pricingUnits.length = 0;
          pricingPlanData["pricingUnits"].forEach(pricingUnitData => {
            this.__addPricingUnitToCache(pricingPlan, pricingUnitData);
          });
          return pricingUnits;
        });
    },

    createPricingUnit: function(pricingPlanId, pricingUnitData) {
      const params = {
        url: {
          "pricingPlanId": pricingPlanId
        },
        data: pricingUnitData
      };
      return osparc.data.Resources.fetch("pricingUnits", "post", params)
        .then(newPricingUnitData => {
          const pricingPlan = this.getPricingPlan(pricingPlanId);
          this.__addPricingUnitToCache(pricingPlan, newPricingUnitData);
          return pricingPlan;
        })
    },

    updatePricingUnit: function(pricingPlanId, pricingUnitId, pricingUnitData) {
      const params = {
        url: {
          "pricingPlanId": pricingPlanId,
          "pricingUnitId": pricingUnitId,
        },
        data: pricingUnitData
      };
      return osparc.data.Resources.fetch("pricingUnits", "post", params)
        .then(() => {
          const pricingPlan = this.getPricingPlan(pricingPlanId);
          // OM do not add but replace
          this.__addPricingUnitToCache(pricingPlan, pricingUnitData);
          return pricingPlan;
        })
    },

    getPricingPlans: function() {
      return this.__pricingPlansCached;
    },

    getPricingPlan: function(pricingPlanId = null) {
      return this.__pricingPlansCached.find(f => f.getPricingPlanId() === pricingPlanId);
    },

    getPricingUnits: function(pricingPlanId) {
      const pricingPlan = this.getPricingPlan(pricingPlanId);
      if (pricingPlan) {
        return pricingPlan.getPricingUnits();
      }
      return null;
    },

    getPricingUnit: function(pricingPlanId, pricingUnitId) {
      const pricingPlan = this.getPricingPlan(pricingPlanId);
      if (pricingPlan) {
        return pricingPlan.getPricingUnits().find(pricingUnit => pricingUnit.getPricingUnitId() === pricingUnitId);
      }
      return null;
    },

    __addToCache: function(pricingPlanData) {
      let pricingPlan = this.__pricingPlansCached.find(f => f.getPricingPlanId() === pricingPlanData["pricingPlanId"]);
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
        this.__pricingPlansCached.unshift(pricingPlan);
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
