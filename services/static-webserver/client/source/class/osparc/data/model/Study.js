/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Class that stores Study data. It is also able to serialize itself.
 *
 *                                    -> {EDGES}
 * STUDY -> METADATA + WORKBENCH ->|
 *                                    -> {LINKS}
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   const study = new osparc.data.model.Study(studyData);
 *   const studyEditor = new osparc.desktop.StudyEditor();
 *   studyEditor.setStudy(study);
 * </pre>
 */

qx.Class.define("osparc.data.model.Study", {
  extend: qx.core.Object,

  /**
   * @param studyData {Object} Object containing the serialized Study Data
   */
  construct: function(studyData) {
    this.base(arguments);

    this.set({
      uuid: studyData.uuid || this.getUuid(),
      workspaceId: studyData.workspaceId || null,
      folderId: studyData.folderId || null,
      name: studyData.name || this.getName(),
      description: studyData.description || this.getDescription(),
      thumbnail: studyData.thumbnail || this.getThumbnail(),
      prjOwner: studyData.prjOwner || this.getPrjOwner(),
      accessRights: studyData.accessRights || this.getAccessRights(),
      creationDate: studyData.creationDate ? new Date(studyData.creationDate) : this.getCreationDate(),
      lastChangeDate: studyData.lastChangeDate ? new Date(studyData.lastChangeDate) : this.getLastChangeDate(),
      classifiers: studyData.classifiers || this.getClassifiers(),
      tags: studyData.tags || this.getTags(),
      state: studyData.state || this.getState(),
      quality: studyData.quality || this.getQuality(),
      permalink: studyData.permalink || this.getPermalink(),
      dev: studyData.dev || this.getDev()
    });

    const wbData = studyData.workbench || this.getWorkbench();
    const workbench = new osparc.data.model.Workbench(wbData, studyData.ui);
    this.setWorkbench(workbench);
    workbench.setStudy(this);

    const workbenchUi = new osparc.data.model.StudyUI(studyData.ui);
    this.setUi(workbenchUi);

    this.getWorkbench().buildWorkbench();
  },

  properties: {
    uuid: {
      check: "String",
      nullable: false,
      event: "changeUuid",
      init: ""
    },

    workspaceId: {
      check: "Number",
      init: null,
      nullable: true,
      event: "changeWorkspaceId"
    },

    folderId: {
      check: "Number",
      init: null,
      nullable: true,
      event: "changeFolderId"
    },

    name: {
      check: "String",
      nullable: false,
      event: "changeName",
      init: "New Study"
    },

    description: {
      check: "String",
      nullable: true,
      event: "changeDescription",
      init: null
    },

    prjOwner: {
      check: "String",
      nullable: false,
      event: "changePrjOwner",
      init: ""
    },

    accessRights: {
      check: "Object",
      nullable: false,
      event: "changeAccessRights",
      apply: "__applyAccessRights",
      init: {}
    },

    creationDate: {
      check: "Date",
      nullable: false,
      event: "changeCreationDate",
      init: new Date()
    },

    lastChangeDate: {
      check: "Date",
      nullable: false,
      event: "changeLastChangeDate",
      init: new Date()
    },

    thumbnail: {
      check: "String",
      nullable: false,
      event: "changeThumbnail",
      init: ""
    },

    workbench: {
      check: "osparc.data.model.Workbench",
      nullable: false,
      event: "changeWorkbench",
      init: {}
    },

    ui: {
      check: "osparc.data.model.StudyUI",
      nullable: true
    },

    tags: {
      check: "Array",
      init: [],
      event: "changeTags",
      nullable: true
    },

    classifiers: {
      check: "Array",
      init: [],
      event: "changeClassifiers",
      nullable: true
    },

    quality: {
      check: "Object",
      init: {},
      event: "changeQuality",
      nullable: true
    },

    permalink: {
      check: "Object",
      nullable: true,
      init: {}
    },

    dev: {
      check: "Object",
      nullable: true,
      init: {}
    },

    // ------ ignore for serializing ------
    state: {
      check: "Object",
      nullable: true,
      event: "changeState",
      apply: "__applyState"
    },

    pipelineRunning: {
      check: "Boolean",
      nullable: true,
      init: false,
      event: "changePipelineRunning"
    },

    readOnly: {
      check: "Boolean",
      nullable: true,
      event: "changeReadOnly",
      init: true
    }
    // ------ ignore for serializing ------
  },

  statics: {
    IgnoreSerializationProps: [
      "permalink",
      "state",
      "pipelineRunning",
      "readOnly"
    ],

    IgnoreModelizationProps: [
      "dev"
    ],

    OwnPatch: [
      "accessRights",
      "workbench"
    ],

    createMinStudyObject: function() {
      let myNewStudyObject = {};
      const props = qx.util.PropertyUtil.getProperties(osparc.data.model.Study);
      for (let key in props) {
        const prop = props[key];
        if (!prop.nullable) {
          if (typeof prop.init === "object") {
            myNewStudyObject[key] = osparc.utils.Utils.deepCloneObject(prop.init);
          } else {
            myNewStudyObject[key] = prop.init;
          }
        }
      }
      return myNewStudyObject;
    },

    getProperties: function() {
      return Object.keys(qx.util.PropertyUtil.getProperties(osparc.data.model.Study));
    },

    // deep clones object with study-only properties
    deepCloneStudyObject: function(obj, ignoreExtra = false) {
      const studyObject = osparc.utils.Utils.deepCloneObject(obj);
      const studyPropKeys = osparc.data.model.Study.getProperties();
      Object.keys(studyObject).forEach(key => {
        if (!studyPropKeys.includes(key)) {
          delete studyObject[key];
        }
        if (ignoreExtra && osparc.data.model.Study.IgnoreSerializationProps.includes(key)) {
          delete studyObject[key];
        }
      });
      return studyObject;
    },

    canIWrite: function(studyAccessRights) {
      const myGroupId = osparc.auth.Data.getInstance().getGroupId();
      const orgIDs = [...osparc.auth.Data.getInstance().getOrgIds()];
      orgIDs.push(myGroupId);
      if (orgIDs.length) {
        return osparc.share.CollaboratorsStudy.canGroupsWrite(studyAccessRights, (orgIDs));
      }
      return false;
    },

    canIDelete: function(studyAccessRights) {
      const myGroupId = osparc.auth.Data.getInstance().getGroupId();
      const orgIDs = [...osparc.auth.Data.getInstance().getOrgIds()];
      orgIDs.push(myGroupId);
      if (orgIDs.length) {
        return osparc.share.CollaboratorsStudy.canGroupsDelete(studyAccessRights, (orgIDs));
      }
      return false;
    },

    hasSlideshow: function(studyData) {
      if ("ui" in studyData && "slideshow" in studyData["ui"] && Object.keys(studyData["ui"]["slideshow"]).length) {
        return true;
      }
      return false;
    },

    getUiMode: function(studyData) {
      if ("ui" in studyData && "mode" in studyData["ui"]) {
        return studyData["ui"]["mode"];
      }
      return null;
    },

    getOutputValue: function(studyData, nodeId, portId) {
      if ("workbench" in studyData &&
        nodeId in studyData["workbench"] &&
        "outputs" in studyData["workbench"][nodeId] &&
        portId in studyData["workbench"][nodeId]["outputs"]
      ) {
        return studyData["workbench"][nodeId]["outputs"][portId];
      }
      return null;
    },

    computeStudyProgress: function(studyData) {
      const nodes = studyData["workbench"];
      let nCompNodes = 0;
      let overallProgress = 0;
      Object.values(nodes).forEach(node => {
        const metadata = osparc.store.Services.getMetadata(node["key"], node["version"]);
        if (metadata && osparc.data.model.Node.isComputational(metadata)) {
          const progress = "progress" in node ? node["progress"] : 0;
          overallProgress += progress;
          nCompNodes++;
        }
      });
      if (nCompNodes === 0) {
        return null;
      }
      return overallProgress/nCompNodes;
    },

    isRunning: function(state) {
      return [
        "PUBLISHED",
        "PENDING",
        "WAITING_FOR_RESOURCES",
        "WAITING_FOR_CLUSTER",
        "STARTED",
        "RETRY"
      ].includes(state);
    }
  },

  members: {
    serialize: function(clean = true) {
      let jsonObject = {};
      const propertyKeys = this.self().getProperties();
      propertyKeys.forEach(key => {
        if (this.self().IgnoreSerializationProps.includes(key)) {
          return;
        }
        if (key === "workbench") {
          jsonObject[key] = this.getWorkbench().serialize(clean);
          return;
        }
        if (key === "ui") {
          jsonObject[key] = this.getUi().serialize();
          return;
        }
        jsonObject[key] = this.get(key);
      });
      return jsonObject;
    },

    initStudy: function() {
      this.getWorkbench().initWorkbench();
    },

    isSnapshot: function() {
      return false;
    },

    getSnapshots: function() {
      return new Promise((resolve, reject) => {
        if (!osparc.data.Permissions.getInstance().canDo("study.snapshot.read")) {
          reject();
          return;
        }
        const params = {
          url: {
            "studyId": this.getUuid()
          }
        };
        osparc.data.Resources.getInstance().getAllPages("snapshots", params)
          .then(snapshots => {
            resolve(snapshots);
          })
          .catch(err => {
            console.error(err);
            reject(err);
          });
      });
    },

    getCurrentSnapshot: function() {
      return new Promise((resolve, reject) => {
        const params = {
          url: {
            "studyId": this.getUuid()
          }
        };
        osparc.data.Resources.fetch("snapshots", "currentCommit", params)
          .then(currentSnapshot => {
            resolve(currentSnapshot);
          })
          .catch(err => {
            console.error(err);
            reject(err);
          });
      });
    },

    getIterations: function() {
      return new Promise((resolve, reject) => {
        if (!osparc.data.Permissions.getInstance().canDo("study.snapshot.read")) {
          reject();
          return;
        }
        this.getCurrentSnapshot()
          .then(snapshot => {
            const params = {
              url: {
                studyId: this.getUuid(),
                snapshotId: snapshot["id"]
              }
            };
            osparc.data.Resources.get("iterations", params)
              .then(iterations => {
                resolve(iterations);
              })
              .catch(err => {
                console.error(err);
                reject(err);
              });
          })
          .catch(err => {
            console.error(err);
            reject(err);
          });
      });
    },

    __getFoldersPath: function(childId, foldersPath = []) {
      foldersPath.unshift(childId);
      const childFolder = osparc.store.Folders.getInstance().getFolder(childId);
      if (childFolder) {
        const parentFolder = osparc.store.Folders.getInstance().getFolder(childFolder.getParentFolderId());
        if (parentFolder) {
          this.__getFoldersPath(parentFolder.getFolderId(), foldersPath);
        }
      }
      return foldersPath;
    },

    getLocationString: function() {
      const location = [];

      if (this.getWorkspaceId()) {
        const workspace = osparc.store.Workspaces.getInstance().getWorkspace(this.getWorkspaceId());
        location.push(workspace.getName());
      } else {
        location.push(qx.locale.Manager.tr("My Workspace"));
      }

      const foldersPathIds = this.__getFoldersPath(this.getFolderId());
      foldersPathIds.forEach(folderId => {
        const folder = osparc.store.Folders.getInstance().getFolder(folderId);
        if (folder) {
          location.push(folder.getName());
        }
      });

      return location.join(" / ");
    },

    // Used for updating some node data through the "nodeUpdated" websocket event
    nodeUpdated: function(nodeUpdatedData) {
      const studyId = nodeUpdatedData["project_id"];
      if (studyId !== this.getUuid()) {
        return;
      }
      const nodeId = nodeUpdatedData["node_id"];
      const nodeData = nodeUpdatedData["data"];
      const workbench = this.getWorkbench();
      const node = workbench.getNode(nodeId);
      // Do not listen to output related backend updates if the node is a frontend node.
      // The frontend controls its output values, progress and states.
      // If a File Picker is uploading a file, the backend could override the current state with some older state.
      if (node && nodeData && !osparc.data.model.Node.isFrontend(node)) {
        node.setOutputData(nodeData.outputs);
        if ("progress" in nodeData) {
          const progress = Number.parseInt(nodeData["progress"]);
          node.getStatus().setProgress(progress);
        }
        node.populateStates(nodeData);
      }
      if (node && "errors" in nodeUpdatedData) {
        const errors = nodeUpdatedData["errors"];
        node.setErrors(errors);
      } else {
        node.setErrors([]);
      }
    },

    nodeNodeProgressSequence: function(nodeProgressData) {
      const studyId = nodeProgressData["project_id"];
      if (studyId !== this.getUuid()) {
        return;
      }
      const nodeId = nodeProgressData["node_id"];
      const workbench = this.getWorkbench();
      const node = workbench.getNode(nodeId);
      if (node) {
        const progressType = nodeProgressData["progress_type"];
        const progressReport = nodeProgressData["progress_report"];
        node.setNodeProgressSequence(progressType, progressReport);
      }
    },

    isLocked: function() {
      if (this.getState() && "locked" in this.getState()) {
        return this.getState()["locked"]["value"];
      }
      return false;
    },

    isPipelineEmpty: function() {
      return Object.keys(this.getWorkbench().getNodes()).length === 0;
    },

    isPipelineMononode: function() {
      return Object.keys(this.getWorkbench().getNodes()).length === 1;
    },

    __applyAccessRights: function(accessRights) {
      if (this.isSnapshot()) {
        this.setReadOnly(true);
      } else {
        const canIWrite = osparc.data.model.Study.canIWrite(accessRights);
        this.setReadOnly(!canIWrite);
      }
    },

    __applyState: function(value) {
      if (value && "state" in value) {
        const isRunning = this.self().isRunning(value["state"]["value"]);
        this.setPipelineRunning(isRunning);
      } else {
        this.setPipelineRunning(false);
      }
    },

    getDisableServiceAutoStart: function() {
      if ("disableServiceAutoStart" in this.getDev()) {
        return this.getDev()["disableServiceAutoStart"];
      }
      return null;
    },

    openStudy: function() {
      const params = {
        url: {
          "studyId": this.getUuid()
        },
        data: osparc.utils.Utils.getClientSessionID()
      };
      if (this.getDisableServiceAutoStart() !== null) {
        params["url"]["disableServiceAutoStart"] = this.getDisableServiceAutoStart();
        return osparc.data.Resources.fetch("studies", "openDisableAutoStart", params);
      }
      return osparc.data.Resources.fetch("studies", "open", params);
    },

    stopStudy: function() {
      this.__stopRequestingStatus();
      this.__stopFileUploads();
      this.__removeIFrames();
    },

    __stopRequestingStatus: function() {
      const nodes = this.getWorkbench().getNodes();
      for (const node of Object.values(nodes)) {
        node.stopRequestingStatus();
      }
    },

    __stopFileUploads: function() {
      const nodes = this.getWorkbench().getNodes();
      for (const node of Object.values(nodes)) {
        if (node.isFilePicker()) {
          node.requestFileUploadAbort();
        }
      }
    },

    __removeIFrames: function() {
      const nodes = this.getWorkbench().getNodes();
      for (const node of Object.values(nodes)) {
        node.removeIFrame();
      }
    },

    getParameters: function() {
      const parameters = [];
      const nodes = this.getWorkbench().getNodes();
      Object.values(nodes).forEach(node => {
        if (node.isParameter()) {
          parameters.push(node);
        }
      });
      return parameters;
    },

    hasSlideshow: function() {
      return !this.getUi().getSlideshow().isEmpty();
    },

    patchStudy: function(studyChanges) {
      const matches = this.self().OwnPatch.filter(el => Object.keys(studyChanges).indexOf(el) !== -1);
      if (matches.length) {
        console.error(matches, "has it's own PATCH path");
        return null;
      }

      return new Promise((resolve, reject) => {
        const params = {
          url: {
            "studyId": this.getUuid()
          },
          data: studyChanges
        };
        osparc.data.Resources.fetch("studies", "patch", params)
          .then(() => {
            Object.keys(studyChanges).forEach(fieldKey => {
              const upKey = qx.lang.String.firstUp(fieldKey);
              const setter = "set" + upKey;
              this[setter](studyChanges[fieldKey]);
            })
            // A bit hacky, but it's not sent back to the backend
            this.set({
              lastChangeDate: new Date()
            });
            const studyData = this.serialize();
            resolve(studyData);
          })
          .catch(err => reject(err));
      });
    },

    /**
     * Call patch Study, but the changes were already applied on the frontend
     * @param studyDiffs {Object} Diff Object coming from the JsonDiffPatch lib. Use only the keys, not the changes.
     */
    patchStudyDelayed: function(studyDiffs) {
      const promises = [];
      let workbenchDiffs = {};
      if ("workbench" in studyDiffs) {
        workbenchDiffs = studyDiffs["workbench"];
        promises.push(this.getWorkbench().patchWorkbenchDelayed(workbenchDiffs));
        delete studyDiffs["workbench"];
      }
      const fieldKeys = Object.keys(studyDiffs);
      if (fieldKeys.length) {
        const patchData = {};
        const params = {
          url: {
            "studyId": this.getUuid()
          },
          data: patchData
        };
        fieldKeys.forEach(fieldKey => {
          if (fieldKey === "ui") {
            patchData[fieldKey] = this.getUi().serialize();
          } else {
            const upKey = qx.lang.String.firstUp(fieldKey);
            const getter = "get" + upKey;
            patchData[fieldKey] = this[getter](studyDiffs[fieldKey]);
          }
          promises.push(osparc.data.Resources.fetch("studies", "patch", params))
        });
      }
      return Promise.all(promises)
        .then(() => {
          // A bit hacky, but it's not sent back to the backend
          this.set({
            lastChangeDate: new Date()
          });
          const studyData = this.serialize();
          return studyData;
        });
    }
  }
});
