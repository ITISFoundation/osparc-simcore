/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2019 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.utils.LibVersions", {
  type: "static",

  statics: {
    getVcsRef: function() {
      return qx.core.Environment.get("osparc.vcsRef");
    },

    getVcsRefUI: function() {
      return qx.core.Environment.get("osparc.vcsRefClient");
    },

    __getRemoteUrl: function() {
      let remoteUrl = qx.core.Environment.get("osparc.vcsOriginUrl");

      if (remoteUrl) {
        remoteUrl = remoteUrl.replace("git@github.com:", "https://github.com/");
        remoteUrl = remoteUrl.replace(".git", "");
      } else {
        remoteUrl = "https://github.com/ITISFoundation/osparc-simcore";
      }

      return remoteUrl;
    },

    getVcsRefUrl: function() {
      const remoteUrl = this.__getRemoteUrl();
      let url = remoteUrl;
      const commitId = this.getVcsRef();
      if (commitId) {
        url = remoteUrl + "/commits/" + String(commitId) + "/";
      }
      return url;
    },

    getVcsRefUIUrl: function() {
      const remoteUrl = this.__getRemoteUrl();
      let url = remoteUrl;
      const commitId = this.getVcsRefUI();
      if (commitId) {
        url = remoteUrl + "/commits/" + String(commitId) + "/services/static-webserver/client/";
      }
      return url;
    },

    getPlatformVersion: function() {
      const name = "osparc-simcore";
      const commitId = this.getVcsRef();
      const remoteUrl = this.getVcsRefUrl();

      return {
        name: name,
        version: commitId.substring(0, 7),
        url: remoteUrl
      };
    },

    getUIVersion: function() {
      let name = "osparc-simcore UI";
      const commitId = this.getVcsRefUI();
      const remoteUrl = this.getVcsRefUIUrl();
      let status = qx.core.Environment.get("osparc.vcsStatusClient");
      if (status) {
        name = name + " [" + status + "]";
      }

      return {
        name: name,
        version: commitId,
        url: remoteUrl
      };
    },

    getQxCompiler: function() {
      return {
        name: "qooxdoo-compiler",
        version: qx.core.Environment.get("qx.compilerVersion"),
        url: "https://github.com/qooxdoo/qooxdoo-compiler"
      };
    },

    getQxLibraryInfoMap: function() {
      const libs = [];
      const libInfo = qx.core.Environment.get("qx.libraryInfoMap");
      if (libInfo) {
        for (let key in libInfo) {
          let lib = libInfo[key];
          libs.push({
            name: lib.name,
            version: lib.version,
            url: lib.homepage
          });
        }
      }
      return libs;
    },

    get3rdPartyLibs: function() {
      const libs = [];
      Object.keys(osparc.wrapper).forEach(className => {
        const wrapper = osparc.wrapper[className];
        libs.push({
          name: wrapper.NAME,
          version: wrapper.VERSION,
          url: wrapper.URL
        });
      });
      return libs;
    },

    getEnvLibs: function() {
      let libs = [];
      [
        osparc.utils.LibVersions.getPlatformVersion,
        osparc.utils.LibVersions.getUIVersion,
        osparc.utils.LibVersions.getQxCompiler,
        osparc.utils.LibVersions.getQxLibraryInfoMap,
        osparc.utils.LibVersions.get3rdPartyLibs
      ].forEach(lib => {
        libs = libs.concat(lib.call(this));
      }, this);

      return libs;
    },

    getBackendLibs: function() {
      const statics = osparc.store.Store.getInstance().get("statics");
      if ("thirdPartyReferences" in statics) {
        return statics["thirdPartyReferences"];
      }
      return [];
    }
  }
});
