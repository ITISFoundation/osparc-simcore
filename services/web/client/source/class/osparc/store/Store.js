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
  type : "singleton",

  properties: {
    currentStudy: {
      check: "osparc.data.model.Study",
      init: null,
      nullable: true
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
    config: {
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
    services: {
      check: "Array",
      init: []
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
    statics: {
      check: "Object",
      init: {}
    }
  },

  events: {
    "servicesRegistered": "qx.event.type.Data"
  },

  members: {
    /**
     * Updates an element or a set of elements in the store.
     * @param {String} resource Name of the resource property. If used with {osparc.data.Resources}, it has to be the same there.
     * @param {*} data Data to be stored, it needs to have the correct type as in the property definition.
     * @param {String} idField Key used for the id field. This field has to be unique among all elements of that resource.
     */
    update: function(resource, data, idField = "uuid") {
      const stored = this.get(resource);
      if (Array.isArray(stored)) {
        if (Array.isArray(data)) {
          this.set(resource, data);
        } else {
          let element = stored.find(item => item[idField] === data[idField]);
          if (element) {
            const newStored = stored.map(item => {
              if (item[idField] === data[idField]) {
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

    /**
     * Remove an element from an array, or erase the store for a given resource.
     * @param {String} resource Name of the resource property. If used with {osparc.data.Resources}, it has to be the same there.
     * @param {String} idField Key used for the id field. This field has to be unique among all elements of that resource.
     * @param {String} id Value of the id field.
     */
    remove: function(resource, idField = "uuid", id) {
      const stored = this.get(resource);
      if (Array.isArray(stored)) {
        const item = stored.find(element => element[idField] === id);
        if (item) {
          const index = stored.indexOf(item);
          this.set(resource, [...stored.slice(0, index), ...stored.slice(index + 1)]);
        }
      } else {
        this.set(resource, {});
      }
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

    getStudyWState: function(studyId, reload = false) {
      return new Promise((resolve, reject) => {
        const studiesWStateCache = this.getStudies();
        const idx = studiesWStateCache.findIndex(studyWStateCache => studyWStateCache["uuid"] === studyId);
        if (!reload && idx !== -1) {
          resolve(studiesWStateCache[idx]);
          return;
        }
        const params = {
          url: {
            "projectId": studyId
          }
        };
        osparc.data.Resources.getOne("studies", params)
          .then(study => {
            osparc.data.Resources.fetch("studies", "state", params)
              .then(state => {
                study["locked"] = state["locked"];
                if (idx === -1) {
                  studiesWStateCache.push(study);
                } else {
                  studiesWStateCache[idx] = study;
                }
                resolve(study);
              })
              .catch(er => {
                console.error(er);
                reject();
              });
          })
          .catch(err => {
            console.error(err);
            reject();
          });
      });
    },

    /**
     * This function provides the list of studies with their state
     * @param {Boolean} reload ?
     */
    getStudiesWState: function(reload = false) {
      return new Promise((resolve, reject) => {
        const studiesWStateCache = this.getStudies();
        if (!reload && studiesWStateCache.length) {
          resolve(studiesWStateCache);
          return;
        }
        studiesWStateCache.length = 0;
        osparc.data.Resources.get("studies")
          .then(studies => {
            const studiesWStatePromises = [];
            studies.forEach(study => {
              const params = {
                url: {
                  "projectId": study.uuid
                }
              };
              studiesWStatePromises.push(osparc.data.Resources.fetch("studies", "state", params));
            });
            Promise.all(studiesWStatePromises)
              .then(studyStates => {
                studyStates.forEach((studyState, idx) => {
                  const study = studies[idx];
                  study["locked"] = studyState["locked"];
                  studiesWStateCache.push(study);
                });
                resolve(studiesWStateCache);
              })
              .catch(er => {
                console.error(er);
                reject();
              });
          })
          .catch(err => {
            console.error(err);
            reject();
          });
      });
    },

    /**
     * This functions does the needed processing in order to have a working list of services and DAGs.
     * @param {Boolean} reload ?
     */
    getServicesDAGs: function(reload) {
      return new Promise((resolve, reject) => {
        const allServices = osparc.utils.Services.getBuiltInServices();
        const servicesPromise = osparc.data.Resources.get("services", null, !reload);
        const dagsPromise = osparc.data.Resources.get("dags", null, !reload);
        Promise.all([servicesPromise, dagsPromise])
          .then(values => {
            allServices.push(...values[0], ...values[1]);
          })
          .catch(err => {
            console.error("getServicesDAGs failed", err);
          })
          .finally(() => {
            const servicesObj = osparc.utils.Services.convertArrayToObject(allServices);
            osparc.utils.Services.servicesToCache(servicesObj, true);
            this.fireDataEvent("servicesRegistered", servicesObj);
            resolve(osparc.utils.Services.servicesCached);
          });
      });
    },

    __getGroups: function(group) {
      return new Promise((resolve, reject) => {
        osparc.data.Resources.getOne("profile")
          .then(profile => {
            resolve(profile["groups"][group]);
          })
          .catch(err => {
            console.error(err);
          });
      });
    },

    getGroupsMe: function() {
      return this.__getGroups("me");
    },

    getGroupsOrganizations: function() {
      return this.__getGroups("organizations");
    },

    getGroupsAll: function() {
      return this.__getGroups("all");
    },

    getGroups: function(withMySelf = true) {
      return new Promise((resolve, reject) => {
        const promises = [];
        promises.push(this.getGroupsOrganizations());
        promises.push(this.getGroupsAll());
        if (withMySelf) {
          promises.push(this.getGroupsMe());
        }
        Promise.all(promises)
          .then(values => {
            const groups = [];
            values[0].forEach(value => {
              groups.push(value);
            });
            groups.push(values[1]);
            if (withMySelf) {
              groups.push(values[2]);
            }
            resolve(groups);
          });
      });
    },

    getVisibleMembers: function() {
      const reachableMembers = this.getReachableMembers();
      return new Promise((resolve, reject) => {
        osparc.data.Resources.get("organizations")
          .then(resp => {
            const orgMembersPromises = [];
            const orgs = resp["organizations"];
            orgs.forEach(org => {
              orgMembersPromises.push(
                new Promise((resolve2, reject2) => {
                  const params = {
                    url: {
                      "gid": org["gid"]
                    }
                  };
                  osparc.data.Resources.get("organizationMembers", params)
                    .then(orgMembers => {
                      resolve2(orgMembers);
                    });
                })
              );
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

    _applyStudy: function(newStudy) {
      if (newStudy) {
        this.setCurrentStudyId(newStudy.getStudyId());
      } else {
        this.setCurrentStudyId(null);
      }
    }
  }
});
