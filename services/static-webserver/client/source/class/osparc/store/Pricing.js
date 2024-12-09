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
      return osparc.data.Resources.getInstance().fetch("pricingPlans", "put", params)
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
      return osparc.data.Resources.fetch("pricingUnits", "get", params)
        .then(pricingPlansData => {
          const pricingPlans = [];
          pricingPlansData.forEach(pricingPlanData => {
            const pricingPlan = this.__addToCache(pricingPlanData);
            pricingPlans.push(pricingPlan);
          });
          return pricingPlans;
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
        const props = Object.keys(qx.util.PropertyUtil.getProperties(osparc.data.model.PricingPlan));
        // put
        Object.keys(pricingPlanData).forEach(key => {
          if (props.includes(key)) {
            pricingPlan.set(key, pricingPlanData[key]);
          }
        });
      } else {
        // get and post
        pricingPlan = new osparc.data.model.PricingPlan(pricingPlanData);
        this.pricingPlansCached.unshift(pricingPlan);
      }
      return pricingPlan;
    },
  }
});
