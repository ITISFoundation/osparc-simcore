/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2025 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.store.Study", {
  extend: qx.core.Object,
  type: "singleton",

  events: {
    "studyStateChanged": "qx.event.type.Data",
    "studyDebtChanged": "qx.event.type.Data",
  },

  members: {
    __nodeResources: null,
    __nodePricingUnit: null,
    __studiesInDebt: null,

    invalidateStudies: function() {
      osparc.store.Store.getInstance().invalidate("studies");
    },

    getPage: function(params, options) {
      return osparc.data.Resources.fetch("studies", "getPage", params, options)
    },

    getPageTrashed: function(params, options) {
      return osparc.data.Resources.fetch("studies", "getPageTrashed", params, options)
    },

    getPageSearch: function(params, options) {
      return osparc.data.Resources.fetch("studies", "getPageSearch", params, options);
    },

    getActive: function(clientSessionID) {
      const params = {
        url: {
          tabId: clientSessionID,
        }
      };
      return osparc.data.Resources.fetch("studies", "getActive", params)
    },

    getOne: function(studyId) {
      const params = {
        url: {
          studyId
        }
      };
      return osparc.data.Resources.fetch("studies", "getOne", params)
    },

    openStudy: function(studyId, autoStart = true) {
      const params = {
        url: {
          studyId,
        },
        data: osparc.utils.Utils.getClientSessionID()
      };
      if (autoStart) {
        return osparc.data.Resources.fetch("studies", "open", params);
      }
      params["url"]["disableServiceAutoStart"] = true;
      return osparc.data.Resources.fetch("studies", "openDisableAutoStart", params);
    },

    closeStudy: function(studyId) {
      const params = {
        url: {
          studyId,
        },
        data: osparc.utils.Utils.getClientSessionID()
      };
      return osparc.data.Resources.fetch("studies", "close", params);
    },

    createStudy: function(studyData) {
      const params = {
        data: studyData
      };
      const options = {
        pollTask: true,
      };
      return osparc.data.Resources.fetch("studies", "postNewStudy", params, options);
    },

    createStudyFromTemplate: function(templateId, studyData) {
      const params = {
        url: {
          templateId,
        },
        data: studyData
      };
      const options = {
        pollTask: true,
      };
      return osparc.data.Resources.fetch("studies", "postNewStudyFromTemplate", params, options);
    },

    duplicateStudy: function(studyId) {
      const params = {
        url: {
          studyId,
        }
      };
      const options = {
        pollTask: true
      };
      return osparc.data.Resources.fetch("studies", "duplicate", params, options);
    },

    deleteStudy: function(studyId) {
      const params = {
        url: {
          studyId
        }
      };
      return osparc.data.Resources.fetch("studies", "delete", params)
        .then(() => {
          osparc.store.Store.getInstance().remove("studies", "uuid", studyId);
        })
        .catch(err => {
          console.error(err);
          throw err;
        });
    },

    patchStudy: function(studyId, patchData) {
      const params = {
        url: {
          studyId,
        },
        data: patchData
      };
      return osparc.data.Resources.fetch("studies", "patch", params);
    },

    patchStudyData: function(studyData, fieldKey, value) {
      if (osparc.data.model.Study.OwnPatch.includes(fieldKey)) {
        console.error(fieldKey, "has it's own PATCH path");
        return null;
      }

      const patchData = {};
      patchData[fieldKey] = value;
      return this.patchStudy(studyData["uuid"], patchData)
        .then(() => {
          studyData[fieldKey] = value;
          // A bit hacky, but it's not sent back to the backend
          studyData["lastChangeDate"] = new Date().toISOString();
        });
    },

    patchTemplateType: function(templateId, templateType) {
      return this.patchStudyData(templateId, "templateType", templateType);
    },

    updateMetadata: function(studyId, metadata) {
      const params = {
        url: {
          studyId,
        },
        data: metadata
      };
      return osparc.data.Resources.fetch("studies", "updateMetadata", params);
    },

    fetchStudyState: function(studyId) {
      osparc.data.Resources.fetch("studies", "state", {
        url: {
          "studyId": studyId
        }
      })
        .then(({state}) => {
          this.setStudyState(studyId, state);
        });
    },

    setStudyState: function(studyId, state) {
      const studiesWStateCache = osparc.store.Store.getInstance().getStudies();
      const idx = studiesWStateCache.findIndex(studyWStateCache => studyWStateCache["uuid"] === studyId);
      if (idx !== -1) {
        studiesWStateCache[idx]["state"] = state;
      }

      const currentStudy = osparc.store.Store.getInstance().getCurrentStudy();
      if (currentStudy && currentStudy.getUuid() === studyId) {
        currentStudy.setState(state);
      }

      this.fireDataEvent("studyStateChanged", {
        studyId,
        state,
      });
    },

    setStudyDebt: function(studyId, debt) {
      // init object if it does not exist
      if (this.__studiesInDebt === null) {
        this.__studiesInDebt = {};
      }
      if (debt) {
        this.__studiesInDebt[studyId] = debt;
      } else {
        delete this.__studiesInDebt[studyId];
      }

      const studiesWStateCache = osparc.store.Store.getInstance().getStudies();
      const idx = studiesWStateCache.findIndex(studyWStateCache => studyWStateCache["uuid"] === studyId);
      if (idx !== -1) {
        if (debt) {
          studiesWStateCache[idx]["debt"] = debt;
        } else {
          delete studiesWStateCache[idx]["debt"];
        }
      }

      this.fireDataEvent("studyDebtChanged", {
        studyId,
        debt,
      });
    },

    getStudyDebt: function(studyId) {
      if (this.__studiesInDebt && studyId in this.__studiesInDebt) {
        return this.__studiesInDebt[studyId];
      }
      return null;
    },

    isStudyInDebt: function(studyId) {
      return Boolean(this.getStudyDebt(studyId));
    },

    payDebt: function(studyId, walletId, amount) {
      const params = {
        url: {
          studyId,
          walletId,
        },
        data: {
          amount,
        }
      };
      return osparc.data.Resources.fetch("studies", "payDebt", params);
    },

    trashStudy: function(studyId) {
      const params = {
        url: {
          studyId
        }
      };
      return osparc.data.Resources.fetch("studies", "trash", params)
        .then(() => {
          osparc.store.Store.getInstance().remove("studies", "uuid", studyId);
        })
        .catch(err => {
          console.error(err);
          throw err;
        });
    },

    untrashStudy: function(studyId) {
      const params = {
        url: {
          studyId
        }
      };
      return osparc.data.Resources.fetch("studies", "untrash", params)
        .catch(err => {
          console.error(err);
          throw err;
        });
    },

    moveStudyToWorkspace: function(studyId, destWorkspaceId) {
      const params = {
        url: {
          studyId,
          workspaceId: destWorkspaceId,
        }
      };
      return osparc.data.Resources.fetch("studies", "moveToWorkspace", params);
    },

    moveStudyToFolder: function(studyId, destFolderId) {
      const params = {
        url: {
          studyId,
          folderId: destFolderId,
        }
      };
      return osparc.data.Resources.fetch("studies", "moveToFolder", params);
    },

    patchNodeData: function(studyData, nodeId, patchData) {
      const params = {
        url: {
          "studyId": studyData["uuid"],
          "nodeId": nodeId
        },
        data: patchData
      };
      return osparc.data.Resources.fetch("studies", "patchNode", params)
        .then(() => {
          Object.keys(patchData).forEach(key => {
            studyData["workbench"][nodeId][key] = patchData[key];
          });
          // A bit hacky, but it's not sent back to the backend
          studyData["lastChangeDate"] = new Date().toISOString();
        });
    },

    getWallet: function(studyId) {
      const params = {
        url: {
          studyId
        }
      };
      return osparc.data.Resources.fetch("studies", "getWallet", params)
        .catch(err => {
          osparc.FlashMessenger.logError(err);
          throw err;
        });
    },

    selectWallet: function(studyId, walletId) {
      const params = {
        url: {
          studyId,
          walletId,
        }
      };
      return osparc.data.Resources.fetch("studies", "selectWallet", params)
        .catch(err => {
          osparc.FlashMessenger.logError(err);
          throw err;
        });
    },

    addTag: function(studyId, tagId) {
      const params = {
        url: {
          tagId,
          studyId,
        }
      };
      return osparc.data.Resources.fetch("studies", "addTag", params)
        .catch(err => {
          console.error(err);
          throw err;
        });
    },

    removeTag: function(studyId, tagId) {
      const params = {
        url: {
          tagId,
          studyId,
        }
      };
      return osparc.data.Resources.fetch("studies", "removeTag", params)
        .catch(err => {
          console.error(err);
          throw err;
        });
    },

    __updateCurrentStudyAccessRights: function(updatedStudyData) {
      const currentStudy = osparc.store.Store.getInstance().getCurrentStudy();
      if (currentStudy && currentStudy.getUuid() === updatedStudyData["uuid"]) {
        currentStudy.set({
          accessRights: updatedStudyData["accessRights"],
          lastChangeDate: new Date(updatedStudyData["lastChangeDate"]),
        });
      }
    },

    addCollaborators: function(studyData, newCollaborators) {
      const promises = [];
      Object.keys(newCollaborators).forEach(gid => {
        const params = {
          url: {
            "studyId": studyData["uuid"],
            "gId": gid
          },
          data: newCollaborators[gid]
        };
        promises.push(osparc.data.Resources.fetch("studies", "postAccessRights", params));
      });
      return Promise.all(promises)
        .then(() => {
          Object.keys(newCollaborators).forEach(gid => {
            studyData["accessRights"][gid] = newCollaborators[gid];
          });
          studyData["lastChangeDate"] = new Date().toISOString();
          this.__updateCurrentStudyAccessRights(studyData);
        })
        .catch(err => {
          osparc.FlashMessenger.logError(err);
          throw err;
        });
    },

    removeCollaborator: function(studyData, gid) {
      const params = {
        url: {
          "studyId": studyData["uuid"],
          "gId": gid
        }
      };
      return osparc.data.Resources.fetch("studies", "deleteAccessRights", params)
        .then(() => {
          delete studyData["accessRights"][gid];
          studyData["lastChangeDate"] = new Date().toISOString();
          this.__updateCurrentStudyAccessRights(studyData);
        })
        .catch(err => {
          osparc.FlashMessenger.logError(err);
          throw err;
        });
    },

    updateCollaborator: function(studyData, gid, newPermissions) {
      const params = {
        url: {
          "studyId": studyData["uuid"],
          "gId": gid
        },
        data: newPermissions
      };
      return osparc.data.Resources.fetch("studies", "putAccessRights", params)
        .then(() => {
          studyData["accessRights"][gid] = newPermissions;
          studyData["lastChangeDate"] = new Date().toISOString();
          this.__updateCurrentStudyAccessRights(studyData);
        })
        .catch(err => {
          osparc.FlashMessenger.logError(err);
          throw err;
        });
    },

    sendShareEmails: function(studyData, selectedEmails, newAccessRights, message) {
      const promises = selectedEmails.map(selectedEmail => {
        const params = {
          url: {
            "studyId": studyData["uuid"],
          },
          data: {
            shareeEmail: selectedEmail,
            sharerMessage: message,
            read: newAccessRights["read"],
            write: newAccessRights["write"],
            delete: newAccessRights["delete"],
          }
        };
        return osparc.data.Resources.fetch("studies", "shareWithEmail", params);
      });
      return Promise.all(promises);
    },

    getNodeResources: function(studyId, nodeId) {
      // init nodeResources if it is null
      if (this.__nodeResources === null) {
        this.__nodeResources = {};
      }

      // check if the resources for this node are already fetched
      if (
        studyId in this.__nodeResources &&
        nodeId in this.__nodeResources[studyId]
      ) {
        return Promise.resolve(this.__nodeResources[studyId][nodeId]);
      }

      const params = {
        url: {
          studyId,
          nodeId,
        }
      };
      return osparc.data.Resources.get("nodesInStudyResources", params)
        .then(resources => {
          // store the fetched resources in the cache
          if (!(studyId in this.__nodeResources)) {
            this.__nodeResources[studyId] = {};
          }
          this.__nodeResources[studyId][nodeId] = resources;
          return resources;
        })
        .catch(err => {
          console.error("Failed to fetch node resources:", err);
          throw err;
        });
    },

    updateNodeResources: function(studyId, nodeId, updatedResources) {
      const params = {
        url: {
          studyId,
          nodeId,
        },
        data: updatedResources
      };
      return osparc.data.Resources.fetch("nodesInStudyResources", "put", params)
        .then(() => {
          // update the cache
          if (!(studyId in this.__nodeResources)) {
            this.__nodeResources[studyId] = {};
          }
          this.__nodeResources[studyId][nodeId] = updatedResources;
        });
    },

    getSelectedPricingUnit: function(studyId, nodeId) {
      // init nodePricingUnit if it is null
      if (this.__nodePricingUnit === null) {
        this.__nodePricingUnit = {};
      }

      // check if the pricing unit for this node is already fetched
      if (
        studyId in this.__nodePricingUnit &&
        nodeId in this.__nodePricingUnit[studyId]
      ) {
        return Promise.resolve(this.__nodePricingUnit[studyId][nodeId]);
      }

      const params = {
        url: {
          studyId,
          nodeId
        }
      };
      return osparc.data.Resources.fetch("studies", "getPricingUnit", params)
        .then(selectedPricingUnit => {
          // store the fetched pricing unit in the cache
          if (!(studyId in this.__nodePricingUnit)) {
            this.__nodePricingUnit[studyId] = {};
          }
          this.__nodePricingUnit[studyId][nodeId] = selectedPricingUnit;
          return selectedPricingUnit;
        })
        .catch(err => {
          console.error("Failed to fetch pricing units:", err);
          throw err;
        });
    },

    updateSelectedPricingUnit: function(studyId, nodeId, planId, selectedPricingUnit) {
      let pricingUnit = null;
      if (selectedPricingUnit instanceof osparc.data.model.PricingUnit) {
        // convert to JSON if it's a model instance
        pricingUnit = JSON.parse(qx.util.Serializer.toJson(selectedPricingUnit));
      } else {
        pricingUnit = osparc.utils.Utils.deepCloneObject(selectedPricingUnit);
      }
      const params = {
        url: {
          studyId,
          nodeId,
          pricingPlanId: planId,
          pricingUnitId: pricingUnit["pricingUnitId"],
        }
      };
      return osparc.data.Resources.fetch("studies", "putPricingUnit", params)
        .then(() => {
          // update the cache
          if (!(studyId in this.__nodePricingUnit)) {
            this.__nodePricingUnit[studyId] = {};
          }
          this.__nodePricingUnit[studyId][nodeId] = pricingUnit;
        })
        .catch(err => {
          console.error("Failed to update selected pricing unit:", err);
          throw err;
        });
    },
  }
});
