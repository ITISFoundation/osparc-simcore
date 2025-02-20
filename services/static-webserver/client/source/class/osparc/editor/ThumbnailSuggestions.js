/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.editor.ThumbnailSuggestions", {
  extend: osparc.widget.SlideBar,

  construct: function(study) {
    this.base(arguments);

    this.set({
      alignX: "center",
      height: 118,
      maxHeight: 118
    });
    this.setButtonsWidth(30);

    this.__thumbnails = [];

    if (study) {
      this.setStudy(study);
    }
  },

  events: {
    "thumbnailAdded": "qx.event.type.Event",
    "thumbnailTapped": "qx.event.type.Data"
  },

  properties: {
    study: {
      check: "osparc.data.model.Study",
      nullable: false,
      init: null,
      apply: "__applyStudyData"
    }
  },

  statics: {
    defaultTemplates: [
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/S4L/Thumbnail-01.png",
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/S4L/Thumbnail-02.png",
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/S4L/Thumbnail-03.png",
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/S4L/Thumbnail-04.png",
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/S4L/Thumbnail-05.png",
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/S4L/Thumbnail-06.png",
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/S4L/Thumbnail-07.png",
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/S4L/Thumbnail-08.png",
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/S4L/Thumbnail-09.png",
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/S4L/Thumbnail-10.png",
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/S4L/Thumbnail-11.png",
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/S4L/Thumbnail-12.png",
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/S4L/Thumbnail-13.png",
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/S4L/Thumbnail-14.png",
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/S4L/Thumbnail-15.png",
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/S4L/Thumbnail-01-b.png",
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/S4L/Thumbnail-02-b.png",
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/S4L/Thumbnail-03-b.png",
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/S4L/Thumbnail-04-b.png",
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/S4L/Thumbnail-05-b.png",
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/S4L/Thumbnail-06-b.png",
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/S4L/Thumbnail-07-b.png",
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/S4L/Thumbnail-08-b.png",
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/S4L/Thumbnail-09-b.png",
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/S4L/Thumbnail-10-b.png",
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/S4L/Thumbnail-11-b.png",
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/S4L/Thumbnail-12-b.png",
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/S4L/Thumbnail-13-b.png",
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/S4L/Thumbnail-14-b.png",
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/S4L/Thumbnail-15-b.png"
    ],
    osparcTemplates: [
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/oSparc/Thumbnail-01.png",
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/oSparc/Thumbnail-02.png",
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/oSparc/Thumbnail-03.png",
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/oSparc/Thumbnail-04.png",
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/oSparc/Thumbnail-05.png",
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/oSparc/Thumbnail-06.png",
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/oSparc/Thumbnail-07.png",
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/oSparc/Thumbnail-08.png",
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/oSparc/Thumbnail-09.png",
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/oSparc/Thumbnail-10.png",
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/oSparc/Thumbnail-11.png",
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/oSparc/Thumbnail-12.png",
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/oSparc/Thumbnail-13.png",
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/oSparc/Thumbnail-14.png"
    ],
    tipTemplates: [
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/TIP/Thumbnail-01.png",
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/TIP/Thumbnail-02.png",
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/TIP/Thumbnail-03.png",
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/TIP/Thumbnail-04.png",
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/TIP/Thumbnail-05.png",
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/TIP/Thumbnail-06.png",
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/TIP/Thumbnail-07.png",
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/TIP/Thumbnail-08.png",
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/TIP/Thumbnail-09.png",
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/TIP/Thumbnail-10.png",
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/TIP/Thumbnail-11.png",
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/TIP/Thumbnail-12.png",
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/TIP/Thumbnail-13.png",
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/TIP/Thumbnail-14.png"
    ],
    /**
     * @param study {osparc.data.model.Study|Object} Study or Serialized Study Object
     */
    extractThumbnailSuggestions: function(study) {
      const queryParams = [];
      const addToQueryParams = (key, version) => {
        const found = queryParams.find(p => p.key === key && p.version === version);
        if (!found) {
          queryParams.push({
            key,
            version
          });
        }
      };
      if (study instanceof osparc.data.model.Study) {
        const wb = study.getWorkbench();
        const nodes = wb.getWorkbenchInitData() ? wb.getWorkbenchInitData() : wb.getNodes();
        Object.values(nodes).forEach(node => addToQueryParams(node.getKey(), node.getVersion()));
      } else {
        const nodes = study["workbench"];
        Object.values(nodes).forEach(node => addToQueryParams(node["key"], node["version"]));
      }

      const promises = [];
      queryParams.forEach(qP => promises.push(osparc.store.Services.getService(qP.key, qP.version)));
      return Promise.all(promises)
        .then(values => {
          const suggestions = new Set([]);
          values.forEach(metadata => {
            if (metadata && metadata["thumbnail"] && !osparc.data.model.Node.isFrontend(metadata)) {
              suggestions.add(metadata["thumbnail"]);
            }
          });
          const defaultThumbnails = this.self().setThumbnailTemplates();
          const amendedArray = [...suggestions, ...defaultThumbnails]
          return Array.from(amendedArray);
        });
    },
    setThumbnailTemplates: function() {
      switch (osparc.product.Utils.getProductName()) {
        case "osparc":
          return this.self().osparcTemplates;
        case "tis":
        case "tiplite":
          return this.self().tipTemplates;
        default:
          return this.self().defaultTemplates.sort();
      }
    }
  },

  members: {
    __thumbnails: null,

    __addThumbnail: function(thumbnailData) {
      this.__thumbnails.push(thumbnailData);
      this.fireEvent("thumbnailAdded");
    },

    __applyStudyData: function(study) {
      this.self().extractThumbnailSuggestions(study)
        .then(suggestions => {
          suggestions.forEach(suggestion => {
            this.__addThumbnail({
              type: "serviceImage",
              thumbnailUrl: suggestion,
              fileUrl: suggestion
            });
          })
          this.__reloadSuggestions();
        });
    },

    addPreviewsToSuggestions: function(previewsPerNodes) {
      previewsPerNodes.forEach(previewsPerNode => {
        const previews = previewsPerNode["screenshots"];
        if (previews && previews.length) {
          previews.forEach(preview => {
            if (preview["mimetype"]) {
              this.__addThumbnail({
                type: preview["mimetype"],
                thumbnailUrl: preview["thumbnail_url"],
                fileUrl: preview["file_url"]
              });
            }
          });
          this.__reloadSuggestions();
        }
      });
    },

    __reloadSuggestions: function() {
      this.setSuggestions(this.__thumbnails);
    },

    __thumbnailTapped: function(thumbnail) {
      // reset decoration
      const unselectedBorderColor = qx.theme.manager.Color.getInstance().resolve("text");
      const unselectedBGColor = qx.theme.manager.Color.getInstance().resolve("fab-background");
      this.getChildren().forEach(thumbnailImg => {
        osparc.utils.Utils.updateBorderColor(thumbnailImg, unselectedBorderColor);
        osparc.utils.Utils.addBackground(thumbnailImg, unselectedBGColor);
      });
      const selectedBorderColor = qx.theme.manager.Color.getInstance().resolve("strong-main");
      const selectedBGColor = qx.theme.manager.Color.getInstance().resolve("background-selected");
      osparc.utils.Utils.updateBorderColor(thumbnail, selectedBorderColor);
      osparc.utils.Utils.addBackground(thumbnail, selectedBGColor);
      this.fireDataEvent("thumbnailTapped", {
        type: thumbnail.thumbnailType || "templateThumbnail",
        source: thumbnail.thumbnailFileUrl || thumbnail.getSource()
      });
    },

    setSuggestions: function(suggestions) {
      this.removeAll();
      suggestions.forEach(suggestion => {
        const maxHeight = this.getMaxHeight() - 21;
        const thumbnail = new osparc.ui.basic.Thumbnail(suggestion.thumbnailUrl || suggestion, maxHeight, null);
        thumbnail.set({
          minWidth: 97,
          margin: 0,
          decorator: "thumbnail"
        });
        thumbnail.thumbnailType = suggestion.type || "templateThumbnail";
        thumbnail.thumbnailFileUrl = suggestion.fileUrl || suggestion;
        thumbnail.addListener("mouseover", () => thumbnail.set({decorator: "thumbnail-selected"}), this);
        thumbnail.addListener("mouseout", () => thumbnail.set({decorator: "thumbnail"}), this);
        thumbnail.addListener("tap", () => this.__thumbnailTapped(thumbnail), this);
        this.add(thumbnail);
      });
    }
  }
});
