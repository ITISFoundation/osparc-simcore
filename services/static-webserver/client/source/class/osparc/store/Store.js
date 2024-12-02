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
    studyBrowserContext: {
      check: ["studiesAndFolders", "workspaces", "search", "trash"],
      init: "studiesAndFolders",
      nullable: false,
      event: "changeStudyBrowserContext",
    },
    studies: {
      check: "Array",
      init: []
    },
    folders: {
      check: "Array",
      init: []
    },
    workspaces: {
      check: "Array",
      init: []
    },
    studyComments: {
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
    clusters: {
      check: "Array",
      init: [],
      event: "changeClusters"
    },
    services: {
      check: "Array",
      init: []
    },
    pricingPlans: {
      check: "Array",
      init: []
    },
    pricingUnits: {
      check: "Array",
      init: []
    },
    billableServices: {
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
    // fetch resources that do not require log in
    preloadCalls: async function() {
      await osparc.data.Resources.get("config");
      await osparc.data.Resources.get("statics");
    },

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
        let propertyKeys;
        if (resources == null) {
          propertyKeys = Object.keys(qx.util.PropertyUtil.getProperties(osparc.store.Store));
        } else if (Array.isArray(resources)) {
          propertyKeys = resources;
        }
        propertyKeys.forEach(propName => {
          // do not reset these resources
          if (["statics", "config"].includes(propName)) {
            return;
          }
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

    trashStudy: function(studyId) {
      const params = {
        url: {
          studyId
        }
      };
      return new Promise((resolve, reject) => {
        osparc.data.Resources.fetch("studies", "trash", params)
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

    untrashStudy: function(studyId) {
      const params = {
        url: {
          studyId
        }
      };
      return new Promise((resolve, reject) => {
        osparc.data.Resources.fetch("studies", "untrash", params)
          .then(() => {
            resolve();
          })
          .catch(err => {
            console.error(err);
            reject(err);
          });
      });
    },

    getTemplate: function(templateId) {
      const templates = this.getTemplates();
      return templates.find(template => template["uuid"] === templateId);
    },

    deleteStudy: function(studyId) {
      const params = {
        url: {
          studyId
        }
      };
      return new Promise((resolve, reject) => {
        osparc.data.Resources.fetch("studies", "delete", params)
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

    getMinimumAmount: function() {
      const defaultMinimum = 10;
      return new Promise(resolve => {
        osparc.data.Resources.fetch("creditPrice", "get")
          .then(data => {
            data && ("minPaymentAmountUsd" in data) ? resolve(data["minPaymentAmountUsd"]) : resolve(defaultMinimum)
          })
          .catch(err => {
            console.error(err);
            resolve(defaultMinimum);
          });
      });
    },

    sortWallets: function(a, b) {
      const aAccessRights = a.getAccessRights();
      const bAccessRights = b.getAccessRights();
      const myGid = osparc.auth.Data.getInstance().getGroupId();
      if (
        aAccessRights &&
        bAccessRights &&
        aAccessRights.find(ar => ar["gid"] === myGid) &&
        bAccessRights.find(ar => ar["gid"] === myGid)
      ) {
        const aAr = aAccessRights.find(ar => ar["gid"] === myGid);
        const bAr = bAccessRights.find(ar => ar["gid"] === myGid);
        const sorted = osparc.share.Collaborators.sortByAccessRights(aAr, bAr);
        if (sorted !== 0) {
          return sorted;
        }
        if (("getName" in a) && ("getName" in b)) {
          return a.getName().localeCompare(b.getName());
        }
        return 0;
      }
      return 0;
    },

    reloadWallets: function() {
      return new Promise((resolve, reject) => {
        osparc.data.Resources.fetch("wallets", "get")
          .then(walletsData => {
            const wallets = [];
            walletsData.forEach(walletReducedData => {
              const wallet = new osparc.data.model.Wallet(walletReducedData);
              wallets.push(wallet);
            });
            this.setWallets(wallets);

            // 1) fetch the access rights
            const accessRightPromises = [];
            this.getWallets().forEach(wallet => {
              accessRightPromises.push(this.reloadWalletAccessRights(wallet));
            });

            Promise.all(accessRightPromises)
              .then(() => {
                wallets.sort(this.sortWallets);
                // 2) depending on the access rights, fetch the auto recharge
                const autoRechargePromises = [];
                this.getWallets().forEach(wallet => {
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
        const groupsStore = osparc.store.Groups.getInstance();
        const orgs = Object.values(groupsStore.getOrganizations());
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
    }
  }
});
