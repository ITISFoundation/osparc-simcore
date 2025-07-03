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

qx.Class.define("osparc.store.Conversations", {
  extend: qx.core.Object,
  type: "singleton",

  events: {
    "conversationRenamed": "qx.event.type.Data",
    "conversationDeleted": "qx.event.type.Data",
  },

  members: {
    getConversations: function(studyId) {
      const params = {
        url: {
          studyId,
          offset: 0,
          limit: 42,
        }
      };
      return osparc.data.Resources.fetch("conversations", "getConversationsPage", params)
        .then(conversations => {
          if (conversations.length) {
            // Sort conversations by created date, oldest first (the new ones will be next to the plus button)
            conversations.sort((a, b) => new Date(a["created"]) - new Date(b["created"]));
          }
          return conversations;
        })
        .catch(err => osparc.FlashMessenger.logError(err));
    },

    addConversation: function(studyId, name = "new 1", type = osparc.study.Conversations.TYPES.PROJECT_STATIC) {
      const params = {
        url: {
          studyId,
        },
        data: {
          name,
          type,
        }
      };
      return osparc.data.Resources.fetch("conversations", "addConversation", params)
        .catch(err => osparc.FlashMessenger.logError(err));
    },

    deleteConversation: function(studyId, conversationId) {
      const params = {
        url: {
          studyId,
          conversationId,
        },
      };
      return osparc.data.Resources.fetch("conversations", "deleteConversation", params)
        .then(() => {
          this.fireDataEvent("conversationDeleted", {
            studyId,
            conversationId,
          })
        })
        .catch(err => osparc.FlashMessenger.logError(err));
    },

    renameConversation: function(studyId, conversationId, name) {
      const params = {
        url: {
          studyId,
          conversationId,
        },
        data: {
          name,
        }
      };
      return osparc.data.Resources.fetch("conversations", "renameConversation", params)
        .then(() => {
          this.fireDataEvent("conversationRenamed", {
            studyId,
            conversationId,
            name,
          });
        })
        .catch(err => osparc.FlashMessenger.logError(err));
    },

    addMessage: function(studyId, conversationId, message) {
      const params = {
        url: {
          studyId,
          conversationId,
        },
        data: {
          "content": message,
          "type": "MESSAGE",
        }
      };
      return osparc.data.Resources.fetch("conversations", "addMessage", params)
        .catch(err => osparc.FlashMessenger.logError(err));
    },

    editMessage: function(studyId, conversationId, messageId, message) {
      const params = {
        url: {
          studyId,
          conversationId,
          messageId,
        },
        data: {
          "content": message,
        },
      };
      return osparc.data.Resources.fetch("conversations", "editMessage", params)
        .catch(err => osparc.FlashMessenger.logError(err));
    },

    deleteMessage: function(message) {
      const params = {
        url: {
          studyId: message["projectId"],
          conversationId: message["conversationId"],
          messageId: message["messageId"],
        },
      };
      return osparc.data.Resources.fetch("conversations", "deleteMessage", params)
        .catch(err => osparc.FlashMessenger.logError(err));
    },

    notifyUser: function(studyId, conversationId, userGroupId) {
      const params = {
        url: {
          studyId,
          conversationId,
        },
        data: {
          "content": userGroupId.toString(), // eventually the backend will accept integers
          "type": "NOTIFICATION",
        }
      };
      return osparc.data.Resources.fetch("conversations", "addMessage", params)
        .catch(err => osparc.FlashMessenger.logError(err));
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
