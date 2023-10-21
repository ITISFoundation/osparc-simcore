/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)
     * Ignacio Pascual (ignapas)

************************************************************************ */

/**
 * Singleton class that stores all the application resources and acts as a cache for them. It is used by {osparc.data.Resources},
 * before making an API call to retrieve resources from the server, it will try to get them from here. Same with post and put calls,
 * their stored elements will be cached here.
 *
 * *Example*
 *
 * Here is a little example of how to use the class. You can get resources like this:
 *
 * <pre class='javascript'>
 *   let studies = osparc.store.Store.getInstance().getStudies();
 * </pre>
 *
 * To invalidate the cache for any of the entities, config for example, just do:
 * <pre class="javascript">
 *   osparc.store.Store.getInstance().resetConfig();
 * </pre>
 * or
 * <pre class="javascript">
 *   osparc.store.Store.getInstance().invalidate("config");
 * </pre>
 * To invalidate the entire cache:
 * <pre class="javascript">
 *   osparc.store.Store.getInstance().invalidate();
 * </pre>
 */
qx.Class.define("osparc.store.Store", {
  extend: qx.core.Object,
  type: "singleton",

  properties: {
    config: {
      check: "Object",
      init: {}
    },
    statics: {
      check: "Object",
      init: {}
    },
    currentStudy: {
      check: "osparc.data.model.Study",
      init: null,
      nullable: true,
      event: "changeCurrentStudy"
    },
    currentStudyId: {
      check: "String",
      init: null,
      nullable: true
    },
    studies: {
      check: "Array",
      init: []
    },
    studyComments: {
      check: "Array",
      init: []
    },
    studyPreviews: {
      check: "Array",
      init: []
    },
    resourceUsage: {
      check: "Array",
      init: []
    },
    nodesInStudyResources: {
      check: "Array",
      init: []
    },
    serviceResources: {
      check: "Array",
      init: []
    },
    snapshots: {
      check: "Array",
      init: [],
      event: "changeSnapshots"
    },
    iterations: {
      check: "Array",
      init: [],
      event: "changeIterations"
    },
    maintenance: {
      check: "Object",
      init: {}
    },
    templates: {
      check: "Array",
      init: []
    },
    profile: {
      check: "Object",
      init: {}
    },
    wallets: {
      check: "Array",
      init: [],
      event: "changeWallets",
      apply: "__applyWallets"
    },
    // If a study with a wallet is opened, this wallet will be the active one
    activeWallet: {
      check: "osparc.data.model.Wallet",
      init: null,
      nullable: true,
      event: "changeActiveWallet",
      apply: "__applyActiveWallet"
    },
    // User's default or primary wallet
    preferredWallet: {
      check: "osparc.data.model.Wallet",
      init: null,
      nullable: true,
      event: "changePreferredWallet",
      apply: "__applyPreferredWallet"
    },
    // activeWallet, preferredWallet or null (in a product with wallets enabled there shouldn't be a null context wallet)
    contextWallet: {
      check: "osparc.data.model.Wallet",
      init: null,
      nullable: true,
      event: "changeContextWallet"
    },
    creditPrice: {
      check: "Number",
      init: null,
      nullable: true,
      event: "changeCreditPrice"
    },
    productMetadata: {
      check: "Object",
      init: {},
      nullable: true
    },
    permissions: {
      check: "Array",
      init: []
    },
    apiKeys: {
      check: "Array",
      init: []
    },
    tokens: {
      check: "Array",
      init: []
    },
    organizations: {
      check: "Object",
      init: {}
    },
    organizationMembers: {
      check: "Object",
      init: {}
    },
    reachableMembers: {
      check: "Object",
      init: {}
    },
    clusters: {
      check: "Array",
      init: [],
      event: "changeClusters"
    },
    services: {
      check: "Array",
      init: []
    },
    portsCompatibility: {
      check: "Object",
      init: {}
    },
    dags: {
      check: "Array",
      init: []
    },
    storageLocations: {
      check: "Array",
      init: []
    },
    tags: {
      check: "Array",
      init: [],
      event: "changeTags"
    },
    classifiers: {
      check: "Array",
      init: null,
      nullable: true,
      event: "changeClassifiers"
    },
    tasks: {
      check: "Array",
      init: []
    }
  },

  members: {
    /**
     * Updates an element or a set of elements in the store.
     * @param {String} resource Name of the resource property. If used with {osparc.data.Resources}, it has to be the same there.
     * @param {*} data Data to be stored, it needs to have the correct type as in the property definition.
     * @param {String} idField Key(s) used for the id field. This field has to be unique among all elements of that resource.
     */
    update: function(resource, data, idField = "uuid") {
      if (data === undefined) {
        return;
      }
      const stored = this.get(resource);
      if (Array.isArray(stored)) {
        if (Array.isArray(data)) {
          this.set(resource, data);
        } else {
          const idFields = Array.isArray(idField) ? idField : [idField];
          const element = stored.find(item => idFields.every(id => item[id] === data[id]));
          if (element) {
            const newStored = stored.map(item => {
              if (idFields.every(id => item[id] === data[id])) {
                return data;
              }
              return item;
            });
            this.set(resource, newStored);
          } else {
            this.set(resource, [...stored, data]);
          }
        }
      } else {
        this.set(resource, data);
      }
    },

    append: function(resource, data) {
      if (data === undefined) {
        return;
      }
      const stored = this.get(resource);
      if (Array.isArray(stored)) {
        this.set(resource, stored.concat(data));
      } else {
        this.set(resource, data);
      }
    },

    /**
     * Remove an element from an array, or erase the store for a given resource.
     * @param {String} resource Name of the resource property. If used with {osparc.data.Resources}, it has to be the same there.
     * @param {String} idField Key(s) used for the id field. This field has to be unique among all elements of that resource.
     * @param {String} id(s) Value of the id field.
     */
    remove: function(resource, idField = "uuid", id) {
      const stored = this.get(resource);
      if (Array.isArray(stored)) {
        const idFields = Array.isArray(idField) ? idField : [idField];
        const ids = Array.isArray(id) ? id : [id];
        const index = stored.findIndex(element => {
          let match = true;
          for (let i=0; i<idFields.length && match; i++) {
            match = element[idFields[i]] === ids[i];
          }
          return match;
        });
        if (index > -1) {
          this.set(resource, [...stored.slice(0, index), ...stored.slice(index + 1)]);
        }
      } else {
        this.set(resource, {});
      }
    },

    // Invalidate the entire cache:
    invalidateEntireCache: function() {
      this.invalidate();
    },

    /**
     * Invalidates the cache for the given resources.
     * If resource is a string, it will invalidate that resource.
     * If it is an array, it will try to invalidate every resource in the array.
     * If it is not provided, it will invalidate all resources.
     *
     * @param {(string|string[])} [resources] Property or array of property names that must be reset
     */
    invalidate: function(resources) {
      if (typeof resources === "string" || resources instanceof String) {
        this.reset(resources);
      } else {
        let propertyArray;
        if (resources == null) {
          propertyArray = Object.keys(qx.util.PropertyUtil.getProperties(osparc.store.Store));
        } else if (Array.isArray(resources)) {
          propertyArray = resources;
        }
        propertyArray.forEach(propName => {
          this.reset(propName);
          // Not sure reset actually works
          const initVal = qx.util.PropertyUtil.getInitValue(this, propName);
          qx.util.PropertyUtil.getUserValue(this, propName, initVal);
        });
      }
    },

    __applyWallets: function(wallets) {
      const preferenceSettings = osparc.Preferences.getInstance();
      const preferenceWalletId = preferenceSettings.getPreferredWalletId();
      if (
        (preferenceWalletId === null || osparc.desktop.credits.Utils.getWallet(preferenceWalletId) === null) &&
        wallets.length === 1
      ) {
        // If there is only one wallet available, make it default
        preferenceSettings.requestChangePreferredWalletId(wallets[0].getWalletId());
      } else if (preferenceWalletId) {
        const walletFound = wallets.find(wallet => wallet.getWalletId() === preferenceWalletId);
        if (walletFound) {
          this.setPreferredWallet(walletFound);
        }
      }
    },

    __applyActiveWallet: function(activeWallet) {
      if (activeWallet) {
        this.setContextWallet(activeWallet);
      } else {
        const preferredWallet = this.getPreferredWallet();
        this.setContextWallet(preferredWallet);
      }
    },

    __applyPreferredWallet: function(preferredWallet) {
      const activeWallet = this.getActiveWallet();
      if (activeWallet === null) {
        this.setContextWallet(preferredWallet);
      }
    },

    getPreferredWallet: function() {
      const wallets = this.getWallets();
      const favouriteWallet = wallets.find(wallet => wallet.isPreferredWallet());
      if (favouriteWallet) {
        return favouriteWallet;
      }
      return null;
    },

    getStudyState: function(studyId) {
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
      const studiesWStateCache = this.getStudies();
      const idx = studiesWStateCache.findIndex(studyWStateCache => studyWStateCache["uuid"] === studyId);
      if (idx !== -1) {
        studiesWStateCache[idx]["state"] = state;
      }

      const currentStudy = this.getCurrentStudy();
      if (currentStudy && currentStudy.getUuid() === studyId) {
        currentStudy.setState(state);
      }
    },

    setTemplateState: function(templateId, state) {
      const templatesWStateCache = this.getTemplates();
      const idx = templatesWStateCache.findIndex(templateWStateCache => templateWStateCache["uuid"] === templateId);
      if (idx !== -1) {
        templatesWStateCache[idx]["state"] = state;
      }
    },

    deleteStudy: function(studyId) {
      const params = {
        url: {
          "studyId": studyId
        }
      };
      return new Promise((resolve, reject) => {
        osparc.data.Resources.fetch("studies", "delete", params, studyId)
          .then(() => {
            this.remove("studies", "uuid", studyId);
            resolve();
          })
          .catch(err => {
            console.error(err);
            reject(err);
          });
      });
    },

    /**
     * @param {String} key
     * @param {String} version
     * @param {Boolean} reload
     */
    getService: function(key, version, reload = false) {
      return new Promise((resolve, reject) => {
        const params = {
          url: osparc.data.Resources.getServiceUrl(key, version)
        };
        osparc.data.Resources.getOne("services", params, null, !reload)
          .then(serviceData => {
            resolve(serviceData);
          });
      });
    },

    /**
     * This functions does the needed processing in order to have a working list of services and DAGs.
     * @param {Boolean} reload
     */
    getAllServices: function(reload = false, includeRetired = true) {
      return new Promise(resolve => {
        let allServices = [];
        osparc.data.Resources.get("services", null, !reload)
          .then(services => {
            allServices = services;
          })
          .catch(err => console.error("getServices failed", err))
          .finally(() => {
            let servicesObj = {};
            if (includeRetired) {
              servicesObj = osparc.service.Utils.convertArrayToObject(allServices);
            } else {
              const nonDepServices = allServices.filter(service => !(osparc.service.Utils.isRetired(service) || osparc.service.Utils.isDeprecated(service)));
              servicesObj = osparc.service.Utils.convertArrayToObject(nonDepServices);
            }
            osparc.service.Utils.addTSRInfo(servicesObj);
            osparc.service.Utils.addExtraTypeInfo(servicesObj);
            if (includeRetired) {
              osparc.service.Utils.servicesCached = servicesObj;
            }
            resolve(servicesObj);
          });
      });
    },

    getInaccessibleServices: function(studyData) {
      return new Promise((resolve, reject) => {
        const inaccessibleServices = [];
        const nodes = Object.values(studyData.workbench);
        nodes.forEach(node => {
          const idx = inaccessibleServices.findIndex(inaccessibleSrv => inaccessibleSrv.key === node.key && inaccessibleSrv.version === node.version);
          if (idx === -1) {
            inaccessibleServices.push({
              key: node["key"],
              version: node["version"],
              label: node["label"]
            });
          }
        });
        this.getAllServices()
          .then(services => {
            nodes.forEach(node => {
              if (osparc.service.Utils.getFromObject(services, node.key, node.version)) {
                const idx = inaccessibleServices.findIndex(inaccessibleSrv => inaccessibleSrv.key === node.key && inaccessibleSrv.version === node.version);
                if (idx !== -1) {
                  inaccessibleServices.splice(idx, 1);
                }
              }
            });
          })
          .catch(err => console.error("failed getting services", err))
          .finally(() => resolve(inaccessibleServices));
      });
    },

    __getGroups: function(group) {
      return new Promise(resolve => {
        osparc.data.Resources.get("organizations")
          .then(groups => {
            resolve(groups[group]);
          })
          .catch(err => console.error(err));
      });
    },

    getGroupsMe: function() {
      return this.__getGroups("me");
    },

    getGroupsOrganizations: function() {
      return this.__getGroups("organizations");
    },

    getProductEveryone: function() {
      return this.__getGroups("product");
    },

    getGroupEveryone: function() {
      return this.__getGroups("all");
    },

    __getAllGroups: function() {
      return new Promise(resolve => {
        const promises = [];
        promises.push(this.getGroupsMe());
        promises.push(this.getVisibleMembers());
        promises.push(this.getGroupsOrganizations());
        promises.push(this.getProductEveryone());
        promises.push(this.getGroupEveryone());
        Promise.all(promises)
          .then(values => {
            const groups = [];
            const groupMe = values[0];
            groupMe["collabType"] = 2;
            groups.push(groupMe);
            const orgMembers = values[1];
            for (const gid of Object.keys(orgMembers)) {
              orgMembers[gid]["collabType"] = 2;
              groups.push(orgMembers[gid]);
            }
            values[2].forEach(org => {
              org["collabType"] = 1;
              groups.push(org);
            });
            const groupProductEveryone = values[3];
            if (groupProductEveryone) {
              groupProductEveryone["collabType"] = 0;
              groups.push(groupProductEveryone);
            }
            const groupEveryone = values[4];
            if (groupEveryone) {
              groupEveryone["collabType"] = 0;
              groups.push(groupEveryone);
            }
            resolve(groups);
          });
      });
    },

    getOrganizationOrUser: function(orgId) {
      return new Promise(resolve => {
        this.__getAllGroups()
          .then(orgs => {
            const idx = orgs.findIndex(org => org.gid === parseInt(orgId));
            if (idx > -1) {
              resolve(orgs[idx]);
            }
            resolve(null);
          });
      });
    },

    getVisibleMembers: function(reload = false) {
      return new Promise(resolve => {
        const reachableMembers = this.getReachableMembers();
        if (!reload && Object.keys(reachableMembers).length) {
          resolve(reachableMembers);
          return;
        }
        osparc.data.Resources.get("organizations")
          .then(resp => {
            const orgMembersPromises = [];
            const orgs = resp["organizations"];
            orgs.forEach(org => {
              const params = {
                url: {
                  "gid": org["gid"]
                }
              };
              orgMembersPromises.push(osparc.data.Resources.get("organizationMembers", params));
            });
            Promise.all(orgMembersPromises)
              .then(orgMemberss => {
                orgMemberss.forEach(orgMembers => {
                  orgMembers.forEach(orgMember => {
                    orgMember["label"] = osparc.utils.Utils.firstsUp(orgMember["first_name"], orgMember["last_name"]);
                    reachableMembers[orgMember["gid"]] = orgMember;
                  });
                });
                resolve(reachableMembers);
              });
          });
      });
    },

    getPotentialCollaborators: function(includeMe = false, includeGlobalEveryone = false) {
      return new Promise((resolve, reject) => {
        const promises = [];
        promises.push(this.getGroupsOrganizations());
        promises.push(this.getVisibleMembers());
        promises.push(this.getProductEveryone());
        promises.push(this.getGroupEveryone());
        Promise.all(promises)
          .then(values => {
            const orgs = values[0]; // array
            const members = values[1]; // object
            const potentialCollaborators = {};
            orgs.forEach(org => {
              if (org["accessRights"]["read"]) {
                org["collabType"] = 1;
                potentialCollaborators[org["gid"]] = org;
              }
            });
            for (const gid of Object.keys(members)) {
              members[gid]["collabType"] = 2;
              potentialCollaborators[gid] = members[gid];
            }
            if (includeMe) {
              const myData = osparc.auth.Data.getInstance();
              const myGid = myData.getGroupId();
              potentialCollaborators[myGid] = {
                "login": myData.getEmail(),
                "first_name": myData.getFirstName(),
                "last_name": myData.getLastName(),
                "collabType": 2
              };
            }
            const productEveryone = values[2]; // entry
            if (productEveryone && productEveryone["accessRights"]["read"]) {
              productEveryone["collabType"] = 0;
              potentialCollaborators[productEveryone["gid"]] = productEveryone;
            }
            const groupEveryone = values[3];
            if (includeGlobalEveryone && groupEveryone) {
              groupEveryone["collabType"] = 0;
              potentialCollaborators[groupEveryone["gid"]] = groupEveryone;
            }
            resolve(potentialCollaborators);
          })
          .catch(err => {
            console.error(err);
            reject(err);
          });
      });
    },

    getGroup: function(gid) {
      return new Promise(resolve => {
        if (gid) {
          this.getPotentialCollaborators()
            .then(potentialCollaborators => {
              let group = null;
              if (gid in potentialCollaborators) {
                group = potentialCollaborators[gid];
              }
              resolve(group);
            })
            .catch(() => resolve(null));
        } else {
          resolve(null);
        }
      });
    },

    getUser: function(uid) {
      return new Promise(resolve => {
        if (uid) {
          this.getVisibleMembers()
            .then(visibleMembers => {
              resolve(Object.values(visibleMembers).find(member => member.id === uid));
            })
            .catch(() => resolve(null));
        } else {
          resolve(null);
        }
      });
    },

    reloadCreditPrice: function() {
      const store = osparc.store.Store.getInstance();
      store.setCreditPrice(null);

      return new Promise(resolve => {
        osparc.data.Resources.fetch("creditPrice", "get")
          .then(data => {
            if (data && data["usdPerCredit"]) {
              store.setCreditPrice(data["usdPerCredit"]);
              resolve(data["usdPerCredit"]);
            }
          });
      });
    },

    reloadWallets: function() {
      const store = osparc.store.Store.getInstance();

      const socket = osparc.wrapper.WebSocket.getInstance();
      const slotName = "walletOsparcCreditsUpdated";
      socket.removeSlot(slotName);
      socket.on(slotName, jsonString => {
        const data = JSON.parse(jsonString);
        const walletFound = store.getWallets().find(wallet => wallet.getWalletId() === parseInt(data["wallet_id"]));
        if (walletFound) {
          walletFound.setCreditsAvailable(parseFloat(data["osparc_credits"]));
        }
      }, this);

      store.setWallets([]);
      return new Promise((resolve, reject) => {
        osparc.data.Resources.fetch("wallets", "get")
          .then(walletsData => {
            const wallets = [];
            walletsData.forEach(walletReducedData => {
              const wallet = new osparc.data.model.Wallet(walletReducedData);
              wallets.push(wallet);
            });
            store.setWallets(wallets);

            // 1) fetch the access rights
            const accessRightPromises = [];
            store.getWallets().forEach(wallet => {
              accessRightPromises.push(this.reloadWalletAccessRights(wallet));
            });

            Promise.all(accessRightPromises)
              .then(() => {
                // 2) depending on the access rights, fetch the auto recharge
                const autoRechargePromises = [];
                store.getWallets().forEach(wallet => {
                  if (wallet.getMyAccessRights() && wallet.getMyAccessRights()["write"]) {
                    autoRechargePromises.push(this.reloadWalletAutoRecharge(wallet));
                  }
                });

                Promise.all(autoRechargePromises)
                  .then(() => resolve())
                  .catch(err => {
                    console.error(err);
                    reject();
                  });
              })
              .catch(err => {
                console.error(err);
                reject();
              });
          })
          .catch(err => {
            console.error(err);
            reject();
          });
      });
    },

    reloadWalletAccessRights: function(wallet) {
      const params = {
        url: {
          "walletId": wallet.getWalletId()
        }
      };
      return osparc.data.Resources.fetch("wallets", "getAccessRights", params)
        .then(accessRights => wallet.setAccessRights(accessRights))
        .catch(err => console.error(err));
    },

    reloadWalletAutoRecharge: function(wallet) {
      const params = {
        url: {
          "walletId": wallet.getWalletId()
        }
      };
      return osparc.data.Resources.fetch("wallets", "getAutoRecharge", params)
        .then(autoRecharge => wallet.setAutoRecharge(autoRecharge))
        .catch(err => console.error(err));
    },

    __getOrgClassifiers: function(orgId, useCache = false) {
      const params = {
        url: {
          "gid": orgId
        }
      };
      return osparc.data.Resources.get("classifiers", params, useCache);
    },

    getAllClassifiers: function(reload = false) {
      return new Promise((resolve, reject) => {
        const oldClassifiers = this.getClassifiers();
        if (!reload && oldClassifiers !== null) {
          resolve(oldClassifiers);
          return;
        }
        this.getGroupsOrganizations()
          .then(orgs => {
            if (orgs.length === 0) {
              this.setClassifiers([]);
              resolve([]);
              return;
            }
            const classifierPromises = [];
            orgs.forEach(org => {
              classifierPromises.push(this.__getOrgClassifiers(org["gid"], !reload));
            });
            Promise.all(classifierPromises)
              .then(orgsClassifiersMD => {
                if (orgsClassifiersMD.length === 0) {
                  this.setClassifiers([]);
                  resolve([]);
                  return;
                }
                const allClassifiers = [];
                orgsClassifiersMD.forEach(orgClassifiersMD => {
                  if ("classifiers" in orgClassifiersMD) {
                    const classifiers = orgClassifiersMD["classifiers"];
                    Object.keys(classifiers).forEach(key => {
                      const classifier = classifiers[key];
                      classifier.key = key;
                      allClassifiers.push(classifier);
                    });
                  }
                });
                this.setClassifiers(allClassifiers);
                resolve(allClassifiers);
              });
          });
      });
    }
  }
});
