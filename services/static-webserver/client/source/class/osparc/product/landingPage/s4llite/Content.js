/* ************************************************************************

   osparc - an entry point to oSparc

   https://osparc.io

   Copyright:
     2020 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.product.landingPage.s4llite.Content", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox().set({
      alignX: "center",
      alignY: "middle"
    }));

    this.buildLayout();
  },

  statics: {
    titleLabel: function(text) {
      const label = new qx.ui.basic.Label().set({
        textAlign: "center",
        rich: true,
        wrap: true
      });
      if (text) {
        label.setValue(text);
      }
      return label;
    },

    smallTitle: function(text) {
      return this.self().titleLabel(text).set({
        font: "text-18",
        width: 200
      });
    },

    mediumTitle: function(text) {
      return this.self().titleLabel(text).set({
        font: "text-22",
        width: 550
      });
    },

    largeTitle: function(text) {
      return this.self().titleLabel(text).set({
        font: "text-26",
        width: 500
      });
    },

    createTabPage: function(title, imageSrc, text) {
      const page = new qx.ui.tabview.Page(title);
      page.setLayout(new qx.ui.layout.HBox(20));
      const tabButton = page.getChildControl("button");
      tabButton.set({
        padding: 10,
        paddingTop: 20,
        paddingBottom: 20,
        alignX: "right"
      });
      tabButton.getChildControl("label").set({
        font: "text-18",
        textAlign: "right",
        alignX: "right",
        width: 280
      });
      const image = new qx.ui.basic.Image(imageSrc).set({
        width: 500,
        height: 300,
        scale: true
      });
      image.getContentElement().setStyles({
        "border-radius": "8px"
      });
      page.add(image);
      const label = new qx.ui.basic.Label(text).set({
        font: "text-16",
        width: 200,
        height: 200,
        rich: true,
        wrap: true,
        alignY: "middle"
      });
      page.add(label);
      return page;
    },

    createVerticalCard: function(imageSrc, title, text) {
      const stepLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(15).set({
        alignX: "center",
        alignY: "middle"
      }));
      const image = new qx.ui.basic.Image(imageSrc).set({
        width: 325,
        height: 230,
        scale: true
      });
      image.getContentElement().setStyles({
        "border-radius": "8px"
      });
      stepLayout.add(image);
      const labelTitle = new qx.ui.basic.Label(title).set({
        font: "text-20",
        textAlign: "center",
        width: 220,
        rich: true,
        wrap: true
      });
      stepLayout.add(labelTitle);
      const labelText = new qx.ui.basic.Label(text).set({
        font: "text-16",
        textAlign: "center",
        width: 225,
        height: 80,
        rich: true,
        wrap: true
      });
      stepLayout.add(labelText);
      return stepLayout;
    },

    lpStrongButton: function(label) {
      const linkButton = new qx.ui.form.Button().set({
        appearance: "strong-button",
        label,
        font: "text-18",
        center: true,
        padding: 12,
        allowGrowX: false,
        width: 170
      });
      linkButton.getContentElement().setStyles({
        "border-radius": "8px"
      });
      return linkButton;
    },

    createLinkButton: function(link) {
      const label = qx.locale.Manager.tr("Try it out");
      const linkButton = this.lpStrongButton(label);
      linkButton.getContentElement().setStyles({
        "border-radius": "8px"
      });
      linkButton.addListener("tap", () => window.open(link, "_blank"));
      return linkButton;
    }
  },

  members: {
    buildLayout: function() {
      [
        this.__createTryItOut(),
        this.__createUsers(),
        this.__createTabbedLeft(),
        this.__createSteps(),
        this.__createPartners(),
        this.__createPhysics(),
        this.__createTestimonials(),
        this.__createTemplates(),
        this.__createCreateAccount(),
        this.__createSubscribe()
      ].forEach((section, idx) => {
        section.setPadding(50);
        if (idx % 2 === 0) {
          section.setBackgroundColor("background-main");
        } else {
          section.setBackgroundColor("background-main-1");
        }
        this._add(section);
      });
    },

    __createTryItOut: function() {
      const contentLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(50).set({
        alignX: "center",
        alignY: "middle"
      }));

      const leftLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(20).set({
        alignX: "center",
        alignY: "middle"
      })).set({
        width: 450,
        maxWidth: 450
      });

      const text1 = new qx.ui.basic.Label().set({
        value: this.tr("Preview the impossible: a native implementation of Sim4Life in the cloud"),
        font: "text-30",
        rich: true,
        wrap: true
      });
      leftLayout.add(text1);

      const text2 = new qx.ui.basic.Label().set({
        value: this.tr("Access it without sacrificing performance and explore the many advantages. Experience the student version <i>S4L<sup>lite</sup></i>."),
        font: "text-20",
        rich: true,
        wrap: true
      });
      leftLayout.add(text2);

      const templateUrl = "https://s4l-lite-master.speag.com/study/6d627670-d872-11ed-bf2e-02420a000d72";
      const tryItOutButton = this.self().createLinkButton(templateUrl);
      leftLayout.add(tryItOutButton);

      contentLayout.add(leftLayout, {
        width: "50%"
      });

      const image = new osparc.ui.basic.ImagePlayLink().set({
        source: "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/lite/extra/bunny.png",
        scale: true,
        alignX: "center",
        maxWidth: 400,
        maxHeight: 300,
        link: templateUrl
      });
      contentLayout.add(image, {
        width: "50%"
      });

      return contentLayout;
    },

    __createUsers: function() {
      const contentLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(20).set({
        alignX: "center",
        alignY: "middle"
      }));

      const text1 = this.self().smallTitle(this.tr("Trusted by 100+ users"));
      contentLayout.add(text1);

      const usersLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
        alignX: "center",
        alignY: "middle"
      }));

      const size = 48;
      [{
        user: "https://github.com/AntoninoMarioC",
        avatar: "https://avatars.githubusercontent.com/u/34208500"
      }, {
        user: "https://github.com/drniiken",
        avatar: "https://avatars.githubusercontent.com/u/32800795"
      }, {
        user: "https://github.com/elisabettai",
        avatar: "https://avatars.githubusercontent.com/u/18575092"
      }, {
        user: "https://github.com/eofli",
        avatar: "https://avatars.githubusercontent.com/u/40888440"
      }, {
        user: "https://github.com/GitHK",
        avatar: "https://avatars.githubusercontent.com/u/5694077"
      }, {
        user: "https://github.com/ignapas",
        avatar: "https://avatars.githubusercontent.com/u/4764217"
      }, {
        user: "https://github.com/mrnicegyu11",
        avatar: "https://avatars.githubusercontent.com/u/8209087"
      }, {
        user: "https://github.com/mguidon",
        avatar: "https://avatars.githubusercontent.com/u/33161876"
      }, {
        user: "https://github.com/matusdrobuliak66",
        avatar: "https://avatars.githubusercontent.com/u/60785969"
      }, {
        user: "https://github.com/odeimaiz",
        avatar: "https://avatars.githubusercontent.com/u/33152403"
      }, {
        user: "https://github.com/pcrespov",
        avatar: "https://avatars.githubusercontent.com/u/32402063"
      }, {
        user: "https://github.com/sanderegg",
        avatar: "https://avatars.githubusercontent.com/u/35365065"
      }, {
        user: "https://github.com/Surfict",
        avatar: "https://avatars.githubusercontent.com/u/4354348"
      }].forEach(user => {
        const link = user.avatar + "?s=" + size;
        const image = new qx.ui.basic.Image().set({
          source: link,
          scale: true,
          maxWidth: size,
          maxHeight: size,
          cursor: "pointer"
        });
        image.addListener("tap", () => window.open(user.user, "_blank"));
        image.getContentElement().setStyles({
          "border-radius": "16px"
        });
        usersLayout.add(image);
      });
      contentLayout.add(usersLayout);

      return contentLayout;
    },

    __createTabbedLeft: function() {
      const contentLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(20).set({
        alignX: "center",
        alignY: "middle"
      }));

      const text1 = this.self().largeTitle(this.tr("Multiphysics simulation platform combining human models with powerful physics solvers"));
      contentLayout.add(text1);

      const tabs = new qx.ui.tabview.TabView().set({
        contentPadding: 20,
        barPosition: "left",
        allowGrowX: false,
        alignX: "center"
      });
      [{
        title: "Whole-body Human Models",
        image: "https://zmt.swiss/assets/images/sim4life/vipnews.png",
        text: "Sim4Life natively supports the Virtual Population ViP 3.x/4.0 models that include integrated posing and morphing tools."
      }, {
        title: "Physics Solvers & Tissue Models",
        image: "https://zmt.swiss/assets/images/sim4life/physics_models/EM01__ResizedImageWzQyMCwyNTFd.jpg",
        text: "The powerful Sim4Life solvers are specifically developed for computationally complex problems, and the integrated tissue models enable the modeling and analysis of physiological processes."
      }, {
        title: "Framework",
        image: "https://zmt.swiss/assets/images/sim4life/framework/_resampled/ResizedImageWzQyMCwyNTBd/postpro01.jpg",
        text: "The Sim4Life Framework efficiently facilitates all steps in complex multiphysics modeling, from defining the problem, discretizing, simulating, and analyzing to visualizing the results, with clarity and flexibility."
      }, {
        title: "Modules",
        image: "https://zmt.swiss/assets/images/sim4life/tissue_models/_resampled/ResizedImageWzQyMCwyNTBd/neuro01.jpg",
        text: "- MRI: IMAnalytics, Musaik, SysSim, BCage, IMSafe, TxCoil<br>- Modeling: Remsesh, iSeg<br>- Calculators: DispFit, PPCalc<br>- Processing: Match, MBSAR, 5G, MiMo, HAC<br>- Import: Huygens, Img, Vox"
      }].forEach(tab => {
        const tabPage = this.self().createTabPage(tab.title, tab.image, tab.text);
        tabs.add(tabPage);
      });
      let i = 0;
      const children = tabs.getChildren();
      setInterval(() => {
        tabs.setSelection([children[i]]);
        i++;
        if (i === children.length) {
          i = 0;
        }
      }, 5000);
      contentLayout.add(tabs);

      return contentLayout;
    },

    __createSteps: function() {
      const contentLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(20).set({
        alignX: "center",
        alignY: "middle"
      }));

      const text1 = this.self().smallTitle(this.tr("HOW IT WORKS"));
      contentLayout.add(text1);

      const text2 = this.self().largeTitle(this.tr("Easy to use, all-in-one solution"));
      contentLayout.add(text2);

      const stepsLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(30).set({
        alignX: "center",
        alignY: "middle"
      }));
      [{
        image: "https://zmt.swiss/assets/images/sim4life/modules/MRI/bcage.png",
        title: "CAD Modeling",
        text: "Use our Virtual Poupualtion, upload CAD models or build your own model with our amazing tools."
      }, {
        image: "https://zmt.swiss/assets/images/sim4life/framework/NewUnstructuredMesh.png",
        title: "Simulation",
        text: "Simulators, gridders, voxelers and solvers"
      }, {
        image: "https://zmt.swiss/assets/images/sim4life/framework/postpromain.jpg",
        title: "Post-processing",
        text: "Analyze simulation results and imaging data through advanced visualization and analysis capabilities."
      }].forEach(tab => {
        const verticalCard = this.self().createVerticalCard(tab.image, tab.title, tab.text);
        stepsLayout.add(verticalCard);
      });
      contentLayout.add(stepsLayout);

      return contentLayout;
    },

    __createPartners: function() {
      const contentLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(20).set({
        alignX: "center",
        alignY: "middle"
      }));

      const text1 = this.self().smallTitle(this.tr("Our partners"));
      contentLayout.add(text1);

      const partnersLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(50).set({
        alignX: "center",
        alignY: "middle"
      }));

      [{
        link: "https://speag.swiss/",
        avatar: "https://speag.swiss/resources/themes/speag/images/logo.png"
      }, {
        link: "https://itis.swiss/",
        avatar: "https://itis.swiss/resources/themes/itis/images/logo.png"
      }, {
        link: "https://zmt.swiss/",
        avatar: "https://d2jx2rerrg6sh3.cloudfront.net/image-handler/picture/2019/10/logo-ZMT-3.png"
      }].forEach(partner => {
        const image = new qx.ui.basic.Image().set({
          source: partner.avatar,
          scale: true,
          maxWidth: 200,
          maxHeight: 50,
          cursor: "pointer"
        });
        image.addListener("tap", () => window.open(partner.link, "_blank"));
        partnersLayout.add(image);
      });
      contentLayout.add(partnersLayout);

      return contentLayout;
    },

    __createPhysics: function() {
      const contentLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(20).set({
        alignX: "center",
        alignY: "middle"
      }));

      const text1 = this.self().smallTitle(this.tr("AVAILABLE PHYSICS"));
      contentLayout.add(text1);

      const text2 = this.self().largeTitle(("A broad range of physics based on best-of-breed simulation solvers"));
      contentLayout.add(text2);

      const grid = new qx.ui.layout.Grid(20, 10);
      const gridLayout = new qx.ui.container.Composite(grid).set({
        allowGrowX: false
      });
      [{
        image: "https://zmt.swiss/assets/images/sim4life/physics_models/EM01b.jpg",
        title: "EM Full Wave",
        text: "Our Electromagnetics Full Wave Solvers offer GPU accelerated, large-scale EM modeling with advanced features such as geometrically adaptive meshes and support for dispersive materials."
      }, {
        image: "https://zmt.swiss/assets/images/sim4life/physics_models/EM02b.jpg",
        title: "Quasi-Static EM",
        text: "Our Quasi-Static Electromagnetic Solvers efficiently model static and quasi-static EM regimes, addressing low-frequency challenges in medical and EM compliance applications."
      }, {
        image: "https://zmt.swiss/assets/images/sim4life/physics_models/thermo01b.jpg",
        title: "Thermodynamics",
        text: "Our Thermodynamic Solvers model heat transfer in living tissue using advanced perfusion and thermoregulation models."
      }, {
        image: "https://zmt.swiss/assets/images/sim4life/tissue_models/vagusnerve.png",
        title: "Neuronal Models",
        text: "Sim4Life's Neuronal Tissue Models dynamically model EM-induced neuronal activity and allow for accurate neural sensing simulations. Our product offers complex multi-compartmental representations and generic models with varying channel dynamics."
      }, {
        image: "https://zmt.swiss/assets/images/sim4life/physics_models/acoustics01B.jpg",
        title: "Acoustics",
        text: "Our Acoustics Solver models pressure wave propagation in highly inhomogeneous media such as tissue and bone. Based on the linear pressure wave equation and optimized for lossy materials, it captures all relevant phenomena like scattering, reflection, and absorption."
      }].forEach((physics, idx) => {
        grid.setColumnAlign(idx, "center", "top");
        grid.setRowAlign(0, "center", "middle"); // image

        const verticalCard = this.self().createVerticalCard(physics.image, physics.title, physics.text);
        const text = verticalCard.getChildren()[2];
        text.set({
          height: 230
        });
        gridLayout.add(text, {
          row: 2,
          column: idx
        });
        gridLayout.add(verticalCard.getChildren()[1], {
          row: 1,
          column: idx
        });
        const image = verticalCard.getChildren()[0];
        image.set({
          width: 225,
          height: 170
        });
        gridLayout.add(image, {
          row: 0,
          column: idx
        });
      });
      contentLayout.add(gridLayout);

      return contentLayout;
    },

    __createTestimonials: function() {
      const contentLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(20).set({
        alignX: "center",
        alignY: "middle"
      }));

      const grid = new qx.ui.layout.Grid(10, 10);
      grid.setColumnAlign(0, "center", "bottom");
      const testimonyGrid = new qx.ui.container.Composite(grid).set({
        allowGrowX: false
      });
      const testimonyImage = new qx.ui.basic.Image().set({
        scale: true,
        maxWidth: 200,
        maxHeight: 50
      });
      testimonyGrid.add(testimonyImage, {
        row: 0,
        column: 0
      });
      const testimonyLabel = new qx.ui.basic.Label().set({
        font: "text-18",
        width: 300,
        rich: true,
        wrap: true,
        textAlign: "center"
      });
      testimonyGrid.add(testimonyLabel, {
        row: 1,
        column: 0
      });
      const testimoneerName = new qx.ui.basic.Label().set({
        font: "text-16",
        width: 300,
        rich: true,
        wrap: true,
        textAlign: "center"
      });
      testimonyGrid.add(testimoneerName, {
        row: 2,
        column: 0
      });
      const testimoneerPosition = new qx.ui.basic.Label().set({
        font: "text-14",
        width: 300,
        rich: true,
        wrap: true,
        textAlign: "center"
      });
      testimonyGrid.add(testimoneerPosition, {
        row: 3,
        column: 0
      });
      contentLayout.add(testimonyGrid);

      const usersLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
        alignX: "center",
        alignY: "middle"
      }));

      const imageSelected = image => {
        image.getContentElement().setStyles({
          "border-width": "2px",
          "border-radius": "16px",
          "border-style": "double",
          "border-color": qx.theme.manager.Color.getInstance().resolve("strong-main")
        });
      };
      const imageUnselected = image => {
        image.getContentElement().setStyles({
          "border-width": "0px",
          "border-radius": "16px"
        });
      };
      const images = [];
      const size = 48;
      [{
        user: "https://media.licdn.com/dms/image/C5603AQHs0nDSqMOHUg/profile-displayphoto-shrink_800_800/0/1583841526403?e=2147483647&v=beta&t=cCyNaotxPTOCWDG9DZm3YJntF92OTgqlCL5T9kZzBfs",
        testimoneerCompany: "https://itis.swiss/resources/themes/itis/images/logo.png",
        testimony: "Thank you guys for your help these past 2 weeks! What an adventure :). Looking forward to the next one!",
        testimoneerName: "Taylor Newton",
        testimoneerPosition: "Descendant of Brook and Isaac"
      }, {
        user: "https://media.licdn.com/dms/image/C4E03AQEPdUlmt0gOZg/profile-displayphoto-shrink_800_800/0/1516647993074?e=2147483647&v=beta&t=Ri3GONAT3ViT2TyzOVvMBRRpEQOiUusnalPMGl4tES8",
        testimoneerCompany: "https://mms.businesswire.com/media/20221108005198/en/1628061/5/9001608_00_logo-ndd.jpg",
        testimony: "Uh oh, I think the study you seek has been deleted from AWS production!",
        testimoneerName: "Katie Zhuang",
        testimoneerPosition: "Technical Product Manager"
      }].forEach((user, idx) => {
        const image = new qx.ui.basic.Image().set({
          source: user.user,
          scale: true,
          maxWidth: size,
          maxHeight: size,
          cursor: "pointer"
        });
        images.push(image);
        image.addListener("tap", () => {
          testimonyImage.setSource(user.testimoneerCompany);
          testimonyLabel.setValue(user.testimony);
          testimoneerName.setValue(user.testimoneerName);
          testimoneerPosition.setValue(user.testimoneerPosition);
        });
        image.getContentElement().setStyles({
          "border-radius": "16px"
        });
        if (idx === 0) {
          testimonyImage.setSource(user.testimoneerCompany);
          testimonyLabel.setValue(user.testimony);
          testimoneerName.setValue(user.testimoneerName);
          testimoneerPosition.setValue(user.testimoneerPosition);
          imageSelected(image);
        }
        usersLayout.add(image);
      });
      images.forEach(image => {
        image.addListener("tap", () => {
          images.forEach(img => imageUnselected(img));
          imageSelected(image);
        });
      });
      contentLayout.add(usersLayout);

      return contentLayout;
    },

    __createTemplates: function() {
      const contentLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(30).set({
        alignX: "center",
        alignY: "middle"
      }));

      const createTemplateCard = (imageSrc, title, link) => {
        const grid = new qx.ui.layout.Grid(10, 10);
        grid.setColumnAlign(0, "center", "bottom");
        const templateCard = new qx.ui.container.Composite(grid).set({
          allowGrowX: false
        });
        const image = new osparc.ui.basic.ImagePlayLink(imageSrc, link, 48).set({
          scale: true,
          maxWidth: 260,
          maxHeight: 160
        });
        templateCard.add(image, {
          row: 0,
          column: 0
        });
        const testimonyLabel = new qx.ui.basic.Label(title).set({
          font: "text-18",
          width: 260,
          rich: true,
          wrap: true,
          textAlign: "center"
        });
        templateCard.add(testimonyLabel, {
          row: 1,
          column: 0
        });
        const tryItOutButton = this.self().createLinkButton(link);
        tryItOutButton.addListener("tap", () => window.open(link, "_blank"));
        templateCard.add(tryItOutButton, {
          row: 2,
          column: 0
        });
        return templateCard;
      };
      [{
        image: "https://zmt.swiss/assets/images/sim4lifeweb/AnimationsFinal/AnimFinal_NewLogo/EM_Phone_Exposure_new.gif",
        title: "EM Full-Wave and Quasi-Static",
        link: "https://https://s4l-lite-master.speag.com/study/58b6d654-5c57-11ed-9d5b-02420a051fc4"
      }, {
        image: "https://zmt.swiss/assets/images/sim4lifeweb/AnimationsFinal/AnimFinal_NewLogo/EM_Neuron_new.gif",
        title: "Coupled EM – Neuro",
        link: "https://https://s4l-lite-master.speag.com/study/58b6d654-5c57-11ed-9d5b-02420a051fc4"
      }, {
        image: "https://zmt.swiss/assets/images/sim4lifeweb/AnimationsFinal/AnimFinal_NewLogo/Thermo_MRILeadPass_new.gif",
        title: "Thermal",
        link: "https://https://s4l-lite-master.speag.com/study/58b6d654-5c57-11ed-9d5b-02420a051fc4"
      }, {
        image: "https://zmt.swiss/assets/images/sim4lifeweb/AnimationsFinal/AnimFinal_NewLogo/AcousticHead_new.gif",
        title: "Acoustics",
        link: "https://https://s4l-lite-master.speag.com/study/58b6d654-5c57-11ed-9d5b-02420a051fc4"
      }].forEach(template => contentLayout.add(createTemplateCard(template.image, template.title, template.link)));
      return contentLayout;
    },

    __createCreateAccount: function() {
      const createAccountLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(15).set({
        alignX: "center",
        alignY: "middle"
      }));

      let message = qx.locale.Manager.tr("Registration is currently only available with an invitation.");
      message += "<br>";
      Promise.all([
        osparc.store.VendorInfo.getInstance().getVendor(),
        osparc.store.StaticInfo.getInstance().getDisplayName()
      ])
        .then(values => {
          const createAccountLabel = this.self().mediumTitle();
          createAccountLayout.add(createAccountLabel);
          const label = this.tr("Request account");
          const requestAccountButton = this.self().lpStrongButton(label);
          createAccountLayout.add(requestAccountButton);
          const vendor = values[0];
          const displayName = values[1];
          if ("invitation_url" in vendor) {
            message += qx.locale.Manager.tr("Please request access to ") + displayName + ":";
            message += "<br>";
            createAccountLabel.setValue(message);
            requestAccountButton.addListener("tap", () => window.open(vendor["invitation_url"], "_blank"));
          } else {
            message += qx.locale.Manager.tr("Please contact:");
            createAccountLabel.setValue(message);
            osparc.store.VendorInfo.getInstance().getSupportEmail()
              .then(supportEmail => {
                const mailto = this.getMailToLabel(supportEmail, "Request Account " + displayName);
                requestAccountButton.addListener("tap", () => window.open(mailto, "_blank"));
              });
          }
        });
      return createAccountLayout;
    },

    __createSubscribe: function() {
      const subscribeLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(15).set({
        alignX: "center",
        alignY: "middle"
      }));

      const subscribeLabel = this.self().mediumTitle(this.tr("Subscribe"));
      subscribeLayout.add(subscribeLabel);

      const height = 48;
      const textFieldLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox().set({
        alignX: "center",
        alignY: "middle"
      }));
      const image = new qx.ui.basic.Image().set({
        source: "@FontAwesome5Solid/envelope/20",
        backgroundColor: "contrasted-text-light",
        textColor: "contrasted-text-dark",
        alignY: "middle",
        alignX: "center",
        paddingTop: 14,
        width: 40,
        height
      });
      textFieldLayout.add(image);
      const email = new qx.ui.form.TextField().set({
        placeholder: this.tr("  Email*"),
        backgroundColor: "contrasted-text-light",
        textColor: "contrasted-text-dark",
        font: "text-16",
        width: 300,
        height
      });
      textFieldLayout.add(email);
      const subscribeButton = new qx.ui.form.Button().set({
        appearance: "strong-button",
        icon: "@FontAwesome5Solid/arrow-right/20",
        font: "text-18",
        alignX: "center",
        alignY: "middle",
        paddingLeft: 14,
        width: 50,
        margin: -1,
        height: height + 2
      });
      textFieldLayout.add(subscribeButton);
      subscribeLayout.add(textFieldLayout);

      return subscribeLayout;
    }
  }
});
