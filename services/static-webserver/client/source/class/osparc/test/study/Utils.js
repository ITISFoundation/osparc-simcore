/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2026 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Tests for osparc.study.Utils.createStudy, the single entry point used by all
 * the different "create a study" flows (empty, from service, from template,
 * from tutorial, from hypertool).
 *
 * The goal is to guarantee that, regardless of the flow, the payload sent to the
 * backend is valid (e.g. a non-empty name, the service node in the workbench,
 * the workspace/folder context, ...). These are exactly the fields the backend
 * rejects with a 422 when they are wrong.
 */
qx.Class.define("osparc.test.study.Utils", {
  extend: qx.dev.unit.TestCase,
  include: [qx.dev.unit.MRequirements, qx.dev.unit.MMock],

  members: {
    __capturedStudyData: null,
    __capturedTemplateId: null,

    setUp: function() {
      this.__capturedStudyData = null;
      this.__capturedTemplateId = null;

      // Bypass the long-running polling task: return the pollPromise as-is so the
      // returned value is whatever the stubbed store call resolves with.
      this.stub(osparc.study.Utils, "__pollCreationTask", pollPromise => pollPromise);

      const studyStore = osparc.store.Study.getInstance();
      // Capture the body that would be POSTed for a brand new study.
      this.stub(studyStore, "createStudy", studyData => {
        this.__capturedStudyData = studyData;
        return Promise.resolve(Object.assign({uuid: "new-study-id"}, studyData));
      });
      // Capture the body that would be POSTed when copying from a template.
      this.stub(studyStore, "createStudyFromTemplate", (templateId, studyData) => {
        this.__capturedTemplateId = templateId;
        this.__capturedStudyData = studyData;
        return Promise.resolve(Object.assign({uuid: "new-study-id"}, studyData));
      });

      // Services layer stubs to keep the test isolated from the network.
      this.stub(osparc.store.Services, "getService", (key, version) => Promise.resolve({
        key,
        version,
        name: "Test Service",
        type: "dynamic",
        thumbnail: "",
      }));
      this.stub(osparc.store.Services, "getStudyServicesMetadata", () => Promise.resolve());
      this.stub(osparc.store.Services, "getInaccessibleServices", () => []);
    },

    tearDown: function() {
      this.getSandbox().restore();
    },

    __templateData: function() {
      return {
        uuid: "template-id",
        resourceType: "template",
        name: "My Template",
        description: "desc",
        thumbnail: "",
        workbench: {},
      };
    },

    /*
    ---------------------------------------------------------------------------
      EMPTY STUDY
    ---------------------------------------------------------------------------
    */
    testEmptyStudyHasName: function() {
      osparc.study.Utils.createStudy({name: "My Empty Study", existingStudies: []})
        .then(() => this.resume(function() {
          const studyData = this.__capturedStudyData;
          this.assertNotNull(studyData, "A study body should have been sent");
          this.assertString(studyData["name"], "name must be a string");
          this.assertTrue(studyData["name"].length > 0, "name must not be empty");
        }, this));
      this.wait(5000);
    },

    testEmptyStudyAppliesContextProps: function() {
      osparc.study.Utils.createStudy({
        name: "My Empty Study",
        existingStudies: [],
        contextProps: {workspaceId: 12, folderId: 34},
      })
        .then(() => this.resume(function() {
          const studyData = this.__capturedStudyData;
          this.assertIdentical(12, studyData["workspaceId"], "workspaceId must be forwarded");
          this.assertIdentical(34, studyData["folderId"], "folderId must be forwarded");
        }, this));
      this.wait(5000);
    },

    /*
    ---------------------------------------------------------------------------
      FROM SERVICE
    ---------------------------------------------------------------------------
    */
    // Regression guard: an undefined label (as emitted by the "+" menu for
    // services) must fall back to the service metadata name, never null.
    testServiceStudyHasNameWhenLabelUndefined: function() {
      osparc.study.Utils.createStudy({
        resourceType: "service",
        serviceKey: "simcore/services/dynamic/test",
        serviceVersion: "1.0.0",
        name: undefined,
        existingStudies: [],
      })
        .then(() => this.resume(function() {
          const studyData = this.__capturedStudyData;
          this.assertString(studyData["name"], "name must be a string");
          this.assertTrue(studyData["name"].length > 0, "name must not be empty");
        }, this));
      this.wait(5000);
    },

    testServiceStudyAddsServiceNode: function() {
      const key = "simcore/services/dynamic/test";
      const version = "1.0.0";
      osparc.study.Utils.createStudy({
        resourceType: "service",
        serviceKey: key,
        serviceVersion: version,
        name: "My Service Study",
        existingStudies: [],
      })
        .then(() => this.resume(function() {
          const workbench = this.__capturedStudyData["workbench"];
          const nodeIds = Object.keys(workbench);
          this.assertIdentical(1, nodeIds.length, "exactly one node must be added");
          const node = workbench[nodeIds[0]];
          this.assertIdentical(key, node["key"], "node key must match the service");
          this.assertIdentical(version, node["version"], "node version must match the service");
        }, this));
      this.wait(5000);
    },

    testServiceStudyAppliesContextProps: function() {
      osparc.study.Utils.createStudy({
        resourceType: "service",
        serviceKey: "simcore/services/dynamic/test",
        serviceVersion: "1.0.0",
        name: "My Service Study",
        existingStudies: [],
        contextProps: {workspaceId: 56, folderId: 78},
      })
        .then(() => this.resume(function() {
          const studyData = this.__capturedStudyData;
          this.assertIdentical(56, studyData["workspaceId"], "workspaceId must be forwarded");
          this.assertIdentical(78, studyData["folderId"], "folderId must be forwarded");
        }, this));
      this.wait(5000);
    },

    /*
    ---------------------------------------------------------------------------
      FROM TEMPLATE / TUTORIAL / HYPERTOOL
    ---------------------------------------------------------------------------
    */
    testTemplateStudyHasNameAndTemplateId: function() {
      osparc.study.Utils.createStudy({
        resourceType: "template",
        templateData: this.__templateData(),
      })
        .then(() => this.resume(function() {
          this.assertIdentical("template-id", this.__capturedTemplateId, "the template uuid must be used");
          const studyData = this.__capturedStudyData;
          this.assertString(studyData["name"], "name must be a string");
          this.assertTrue(studyData["name"].length > 0, "name must not be empty");
        }, this));
      this.wait(5000);
    },

    testTemplateStudyAppliesContextProps: function() {
      osparc.study.Utils.createStudy({
        resourceType: "template",
        templateData: this.__templateData(),
        contextProps: {workspaceId: 90, folderId: 12},
      })
        .then(() => this.resume(function() {
          const studyData = this.__capturedStudyData;
          this.assertIdentical(90, studyData["workspaceId"], "workspaceId must be forwarded");
          this.assertIdentical(12, studyData["folderId"], "folderId must be forwarded");
        }, this));
      this.wait(5000);
    },

    // tutorial and hypertool must route through the same template based flow
    testTutorialRoutesThroughTemplateFlow: function() {
      osparc.study.Utils.createStudy({
        resourceType: "tutorial",
        templateData: this.__templateData(),
      })
        .then(() => this.resume(function() {
          this.assertIdentical("template-id", this.__capturedTemplateId, "tutorial must copy from the template uuid");
        }, this));
      this.wait(5000);
    }
  }
});
