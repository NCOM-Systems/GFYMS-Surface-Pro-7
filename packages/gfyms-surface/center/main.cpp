#include <QApplication>
#include <QClipboard>
#include <QCryptographicHash>
#include <QDateTime>
#include <QDesktopServices>
#include <QDir>
#include <QFileDialog>
#include <QFile>
#include <QGroupBox>
#include <QHBoxLayout>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QLabel>
#include <QListWidget>
#include <QMainWindow>
#include <QMessageBox>
#include <QNetworkAccessManager>
#include <QNetworkReply>
#include <QNetworkRequest>
#include <QProgressBar>
#include <QProcess>
#include <QPushButton>
#include <QSettings>
#include <QSlider>
#include <QTabWidget>
#include <QTextBrowser>
#include <QUrl>
#include <QVBoxLayout>
#include <QComboBox>
#include <QStringList>
#include <functional>
#include <QCheckBox>
#include <QTimer>

namespace {
constexpr auto kReleasesUrl = "https://api.github.com/repos/pfn000/GFYMS-Surface-Pro-7/releases";
constexpr auto kDiscussionsUrl = "https://github.com/pfn000/GFYMS-Surface-Pro-7/discussions";

QString readText(const QString &path, const QString &fallback)
{
    QFile file(path);
    if (!file.open(QIODevice::ReadOnly | QIODevice::Text)) return fallback;
    const QString value = QString::fromUtf8(file.readAll()).trimmed();
    return value.isEmpty() ? fallback : value;
}

QString doctorReport()
{
    QProcess process;
    process.start(QStringLiteral("/usr/bin/gfyms"), {QStringLiteral("doctor")});
    if (!process.waitForFinished(10000)) {
        process.kill();
        return QStringLiteral("GFYMS doctor timed out.");
    }
    return QString::fromLocal8Bit(process.readAllStandardOutput() + process.readAllStandardError()).trimmed();
}

QStringList packageAssets(const QJsonArray &assets)
{
    QStringList result;
    for (const auto &item : assets) {
        const auto asset = item.toObject();
        const QString name = asset.value(QStringLiteral("name")).toString();
        if (name.startsWith(QStringLiteral("gfyms-")) && name.endsWith(QStringLiteral(".pkg.tar.zst"))) {
            result.push_back(name);
        }
    }
    return result;
}

QString assetUrl(const QJsonArray &assets, const QString &name)
{
    for (const auto &item : assets) {
        const auto asset = item.toObject();
        if (asset.value(QStringLiteral("name")).toString() == name) return asset.value(QStringLiteral("browser_download_url")).toString();
    }
    return {};
}

QString expectedHash(const QByteArray &contents, const QString &name)
{
    for (const auto &line : contents.split('\n')) {
        const auto parts = line.simplified().split(' ');
        if (parts.size() >= 2 && QString::fromUtf8(parts.last()) == name) return QString::fromUtf8(parts.first()).toLower();
    }
    return {};
}
}

class GfymsCenter final : public QMainWindow
{
public:
    GfymsCenter()
        : network_(new QNetworkAccessManager(this))
    {
        setWindowTitle(QStringLiteral("GFYMS Center"));
        resize(1080, 760);
        setStyleSheet(QStringLiteral(
            "QWidget{background:#101216;color:#f5f6f8;}"
            "QTabWidget::pane{border:1px solid #2a2f38;border-radius:24px;}"
            "QTabBar::tab{background:#191d23;padding:12px 18px;margin:4px;border-radius:24px;}"
            "QTabBar::tab:selected{background:#2c3340;}"
            "QGroupBox{border:1px solid #2a2f38;border-radius:24px;margin-top:12px;padding:18px;}"
            "QPushButton{background:#252b35;border:1px solid #343b47;border-radius:24px;padding:11px 18px;}"
            "QPushButton:hover{background:#303744;}"
            "QTextBrowser,QListWidget,QComboBox{background:#171a20;border:1px solid #303744;border-radius:24px;padding:8px;}"
            "QSlider::groove:horizontal{height:8px;border-radius:4px;background:#292f39;}"
            "QSlider::handle:horizontal{width:22px;margin:-7px 0;border-radius:11px;background:#f5f6f8;}"
            "QProgressBar{background:#171a20;border:1px solid #303744;border-radius:24px;text-align:center;}"
        ));

        auto *tabs = new QTabWidget(this);
        setCentralWidget(tabs);
        tabs->addTab(buildOverview(), QStringLiteral("Overview"));
        tabs->addTab(buildPen(), QStringLiteral("Surface Pen"));
        tabs->addTab(buildFindMy(), QStringLiteral("Find My"));
        tabs->addTab(buildUpdates(), QStringLiteral("Updates"));
        tabs->addTab(buildFeedback(), QStringLiteral("Feedback"));
        loadReleases();

        auto *updateTimer = new QTimer(this);
        updateTimer->setInterval(6 * 60 * 60 * 1000);
        connect(updateTimer, &QTimer::timeout, this, &GfymsCenter::loadReleases);
        updateTimer->start();
    }

private:
    QWidget *buildOverview()
    {
        auto *page = new QWidget;
        auto *layout = new QVBoxLayout(page);
        auto *title = new QLabel(QStringLiteral("GFYMS Center"));
        title->setStyleSheet(QStringLiteral("font-size:30px;font-weight:700;"));
        layout->addWidget(title);
        layout->addWidget(new QLabel(QStringLiteral("Surface Pro 7 controls, update management, diagnostics and recovery.")));

        auto *box = new QGroupBox(QStringLiteral("Device"));
        auto *form = new QVBoxLayout(box);
        form->addWidget(new QLabel(QStringLiteral("Product: ") + readText(QStringLiteral("/sys/class/dmi/id/product_name"), QStringLiteral("Unknown"))));
        form->addWidget(new QLabel(QStringLiteral("Kernel: ") + readText(QStringLiteral("/proc/sys/kernel/osrelease"), QStringLiteral("Unknown"))));
        form->addWidget(new QLabel(QStringLiteral("GFYMS: ") + readText(QStringLiteral("/usr/share/gfyms/version"), QStringLiteral("Development build"))));
        auto *doctor = new QPushButton(QStringLiteral("Run GFYMS Doctor"));
        connect(doctor, &QPushButton::clicked, this, [this] { QMessageBox::information(this, QStringLiteral("GFYMS Doctor"), doctorReport()); });
        form->addWidget(doctor);
        layout->addWidget(box);
        layout->addStretch();
        return page;
    }

    QWidget *buildPen()
    {
        auto *page = new QWidget;
        auto *layout = new QVBoxLayout(page);
        auto *box = new QGroupBox(QStringLiteral("Surface Pen"));
        auto *form = new QVBoxLayout(box);

        auto *pressure = new QSlider(Qt::Horizontal);
        pressure->setRange(0, 100);
        pressure->setValue(settings_.value(QStringLiteral("pen/pressure"), 50).toInt());
        auto *pressureLabel = new QLabel;
        auto refreshPressure = [this, pressure, pressureLabel] {
            settings_.setValue(QStringLiteral("pen/pressure"), pressure->value());
            pressureLabel->setText(QStringLiteral("Pressure response: %1").arg(pressure->value()));
        };
        refreshPressure();
        connect(pressure, &QSlider::valueChanged, this, [refreshPressure](int) { refreshPressure(); });
        form->addWidget(pressureLabel);
        form->addWidget(pressure);

        form->addWidget(new QLabel(QStringLiteral("Writing hand")));
        auto *hand = new QComboBox;
        hand->addItems({QStringLiteral("Right handed"), QStringLiteral("Left handed")});
        hand->setCurrentIndex(settings_.value(QStringLiteral("pen/hand"), 0).toInt());
        connect(hand, &QComboBox::currentIndexChanged, this, [this](int value) {
            settings_.setValue(QStringLiteral("pen/hand"), value);
        });
        form->addWidget(hand);

        form->addWidget(new QLabel(QStringLiteral("Top button")));
        auto *topButton = new QComboBox;
        topButton->addItems({
            QStringLiteral("Open GFYMS Center"),
            QStringLiteral("Show launcher"),
            QStringLiteral("Screenshot"),
            QStringLiteral("Do nothing")
        });
        topButton->setCurrentIndex(settings_.value(QStringLiteral("pen/top-button"), 0).toInt());
        connect(topButton, &QComboBox::currentIndexChanged, this, [this](int value) {
            settings_.setValue(QStringLiteral("pen/top-button"), value);
        });
        form->addWidget(topButton);

        form->addWidget(new QLabel(QStringLiteral("Side button")));
        auto *sideButton = new QComboBox;
        sideButton->addItems({
            QStringLiteral("Right click"),
            QStringLiteral("Middle click"),
            QStringLiteral("Do nothing")
        });
        sideButton->setCurrentIndex(settings_.value(QStringLiteral("pen/side-button"), 0).toInt());
        connect(sideButton, &QComboBox::currentIndexChanged, this, [this](int value) {
            settings_.setValue(QStringLiteral("pen/side-button"), value);
        });
        form->addWidget(sideButton);

        auto *status = new QLabel(QStringLiteral("Pen battery/status: use BlueZ/UPower when the pen exposes a battery service."));
        status->setWordWrap(true);
        form->addWidget(status);

        auto *info = new QLabel(QStringLiteral(
            "These controls mirror the category of settings Microsoft provides in the Surface app. "
            "The final hardware backend will route them through GFYMS IPTS/HID/uinput integration."
        ));
        info->setWordWrap(true);
        form->addWidget(info);

        layout->addWidget(box);
        layout->addStretch();
        return page;
    }

    QWidget *buildFindMy()
    {
        auto *page = new QWidget;
        auto *layout = new QVBoxLayout(page);
        auto *box = new QGroupBox(QStringLiteral("Find My Bridge"));
        auto *form = new QVBoxLayout(box);

        auto *info = new QLabel(QStringLiteral(
            "Optional OpenHaystack-compatible BLE beacon mode. Nearby Apple devices may relay the encrypted beacon. "
            "This is not Apple's official Find My device-registration flow."
        ));
        info->setWordWrap(true);
        form->addWidget(info);

        auto *importKey = new QPushButton(QStringLiteral("Import advertisement key"));
        auto *enable = new QPushButton(QStringLiteral("Enable beacon"));
        auto *disable = new QPushButton(QStringLiteral("Disable beacon"));
        auto *docs = new QPushButton(QStringLiteral("Open Find My documentation"));

        connect(importKey, &QPushButton::clicked, this, [] {
            const QString path = QFileDialog::getOpenFileName(nullptr, QStringLiteral("Import OpenHaystack advertisement key"));
            if (path.isEmpty()) return;
            const int code = QProcess::execute(QStringLiteral("pkexec"),
                {QStringLiteral("/usr/bin/gfyms-findmy"), QStringLiteral("import"), path});
            if (code != 0) {
                QMessageBox::warning(nullptr, QStringLiteral("Find My"), QStringLiteral("The advertisement key was not imported."));
            }
        });
        connect(enable, &QPushButton::clicked, [] {
            QProcess::startDetached(QStringLiteral("pkexec"), {QStringLiteral("/usr/bin/gfyms-findmy"), QStringLiteral("enable")});
        });
        connect(disable, &QPushButton::clicked, [] {
            QProcess::startDetached(QStringLiteral("pkexec"), {QStringLiteral("/usr/bin/gfyms-findmy"), QStringLiteral("disable")});
        });
        connect(docs, &QPushButton::clicked, [] {
            QDesktopServices::openUrl(QUrl(QStringLiteral("https://github.com/pfn000/GFYMS-Surface-Pro-7/blob/main/docs/GFYMS-FIND-MY.md")));
        });

        form->addWidget(importKey);
        form->addWidget(enable);
        form->addWidget(disable);
        form->addWidget(docs);
        layout->addWidget(box);
        layout->addStretch();
        return page;
    }

    QWidget *buildUpdates()
    {
        auto *page = new QWidget;
        auto *layout = new QVBoxLayout(page);
        auto *split = new QHBoxLayout;
        releases_ = new QListWidget;
        notes_ = new QTextBrowser;
        split->addWidget(releases_, 2);
        split->addWidget(notes_, 3);
        layout->addLayout(split);

        auto *buttons = new QHBoxLayout;
        auto *install = new QPushButton(QStringLiteral("Install selected"));
        auto *rollback = new QPushButton(QStringLiteral("Undo last GFYMS update"));
        auto *refresh = new QPushButton(QStringLiteral("Check for updates"));
        auto *autoUpdate = new QCheckBox(QStringLiteral("Automatically install stable GFYMS updates"));
        {
            QProcess process;
            process.start(QStringLiteral("/usr/libexec/gfyms-update-helper"), {QStringLiteral("get-auto")});
            if (process.waitForFinished(1500) && process.exitCode() == 0) {
                autoUpdate->setChecked(QString::fromLocal8Bit(process.readAllStandardOutput()).trimmed() == QStringLiteral("1"));
            }
        }
        connect(autoUpdate, &QCheckBox::toggled, this, [](bool checked) {
            QProcess::startDetached(QStringLiteral("pkexec"),
                {QStringLiteral("/usr/libexec/gfyms-update-helper"), QStringLiteral("set-auto"),
                 checked ? QStringLiteral("1") : QStringLiteral("0")});
        });
        buttons->addWidget(install);
        buttons->addWidget(rollback);
        buttons->addWidget(refresh);
        layout->addLayout(buttons);
        layout->addWidget(autoUpdate);

        progress_ = new QProgressBar;
        progress_->setRange(0, 100);
        layout->addWidget(progress_);

        connect(releases_, &QListWidget::currentRowChanged, this, [this](int row) {
            if (row < 0 || row >= releasesData_.size()) return;
            const auto release = releasesData_.at(row).toObject();
            notes_->setMarkdown(QStringLiteral("# %1\n\n%2")
                .arg(release.value(QStringLiteral("tag_name")).toString(),
                     release.value(QStringLiteral("body")).toString()));
        });
        connect(refresh, &QPushButton::clicked, this, &GfymsCenter::loadReleases);
        connect(install, &QPushButton::clicked, this, &GfymsCenter::installSelected);
        connect(rollback, &QPushButton::clicked, this, &GfymsCenter::rollback);
        return page;
    }

    QWidget *buildFeedback()
    {
        auto *page = new QWidget;
        auto *layout = new QVBoxLayout(page);
        auto *text = new QLabel(QStringLiteral(
            "Keep regressions and feature requests tied to the exact GFYMS release. "
            "GFYMS can copy a diagnostic report and open the repository Discussions page."
        ));
        text->setWordWrap(true);
        layout->addWidget(text);

        auto *report = new QPushButton(QStringLiteral("Copy diagnostics + open Discussions"));
        connect(report, &QPushButton::clicked, [this] {
            QApplication::clipboard()->setText(doctorReport());
            QDesktopServices::openUrl(QUrl(QString::fromLatin1(kDiscussionsUrl)));
        });
        layout->addWidget(report);

        auto *open = new QPushButton(QStringLiteral("Open GitHub Discussions"));
        connect(open, &QPushButton::clicked, [] {
            QDesktopServices::openUrl(QUrl(QString::fromLatin1(kDiscussionsUrl)));
        });
        layout->addWidget(open);
        layout->addStretch();
        return page;
    }

    void loadReleases()
    {
        notes_->setMarkdown(QStringLiteral("Checking GitHub Releases…"));
        QNetworkRequest request{QUrl(QString::fromLatin1(kReleasesUrl))};
        request.setHeader(QNetworkRequest::UserAgentHeader, QStringLiteral("GFYMS-Center"));
        auto *reply = network_->get(request);
        connect(reply, &QNetworkReply::finished, this, [this, reply] {
            reply->deleteLater();
            if (reply->error() != QNetworkReply::NoError) {
                notes_->setMarkdown(QStringLiteral("Update check failed: %1").arg(reply->errorString()));
                return;
            }
            const auto doc = QJsonDocument::fromJson(reply->readAll());
            if (!doc.isArray()) {
                notes_->setMarkdown(QStringLiteral("GitHub returned an invalid release list."));
                return;
            }
            releasesData_ = doc.array();
            releases_->clear();
            for (const auto &item : releasesData_) {
                releases_->addItem(item.toObject().value(QStringLiteral("tag_name")).toString());
            }
            if (!releasesData_.isEmpty()) releases_->setCurrentRow(0);
        });
    }

    void installSelected()
    {
        const int row = releases_->currentRow();
        if (row < 0 || row >= releasesData_.size()) {
            QMessageBox::warning(this, QStringLiteral("GFYMS Updates"), QStringLiteral("Select a release."));
            return;
        }

        const auto release = releasesData_.at(row).toObject();
        const auto assets = release.value(QStringLiteral("assets")).toArray();
        const QStringList names = packageAssets(assets);
        if (names.isEmpty()) {
            QMessageBox::warning(this, QStringLiteral("GFYMS Updates"), QStringLiteral("That release contains no GFYMS package assets."));
            return;
        }

        const QString sumsUrl = assetUrl(assets, QStringLiteral("SHA256SUMS"));
        const auto continueWithSums = [this, release, assets, names](const QByteArray &sums) {
            const QString tempRoot = QDir::temp().filePath(QStringLiteral("gfyms-update-%1").arg(QDateTime::currentMSecsSinceEpoch()));
            QDir().mkpath(tempRoot);
            auto *replyState = new QStringList;
            auto *networkReplyState = new QList<QNetworkReply *>;
            auto *failed = new bool(false);

            std::function<void(int)> downloadNext;
            downloadNext = [this, release, assets, names, sums, tempRoot, replyState, networkReplyState, failed, downloadNext](int index) mutable {
                if (*failed) return;
                if (index >= names.size()) {
                    for (auto *reply : std::as_const(*networkReplyState)) reply->deleteLater();
                    const QStringList paths = *replyState;
                    const int code = QProcess::execute(QStringLiteral("pkexec"),
                        QStringList{QStringLiteral("/usr/libexec/gfyms-update-helper"), QStringLiteral("install")} + paths);
                    progress_->setValue(100);
                    if (code == 0) {
                        QMessageBox::information(this, QStringLiteral("GFYMS Update"),
                            QStringLiteral("GFYMS release %1 installed. Reboot if the release changed kernel integration.")
                                .arg(release.value(QStringLiteral("tag_name")).toString()));
                        loadReleases();
                    } else {
                        QMessageBox::critical(this, QStringLiteral("GFYMS Update"), QStringLiteral("The GFYMS package set was not installed."));
                    }
                    return;
                }

                const QString name = names.at(index);
                const QString url = assetUrl(assets, name);
                if (url.isEmpty()) {
                    *failed = true;
                    QMessageBox::critical(this, QStringLiteral("GFYMS Update"), QStringLiteral("Release asset is missing: %1").arg(name));
                    return;
                }

                QNetworkRequest request{QUrl(url)};
                request.setHeader(QNetworkRequest::UserAgentHeader, QStringLiteral("GFYMS-Center"));
                auto *reply = network_->get(request);
                networkReplyState->push_back(reply);
                connect(reply, &QNetworkReply::downloadProgress, this, [this, index, total = names.size()](qint64 done, qint64 totalBytes) {
                    if (totalBytes <= 0) return;
                    const int perFile = static_cast<int>((done * 100) / totalBytes);
                    progress_->setValue((index * 100 + perFile) / total);
                });
                connect(reply, &QNetworkReply::finished, this, [this, reply, replyState, failed, sums, tempRoot, name, downloadNext, index] () mutable {
                    if (reply->error() != QNetworkReply::NoError) {
                        *failed = true;
                        reply->deleteLater();
                        QMessageBox::critical(this, QStringLiteral("GFYMS Update"), reply->errorString());
                        return;
                    }

                    const QString path = QDir(tempRoot).filePath(name);
                    QFile package(path);
                    if (!package.open(QIODevice::WriteOnly)) {
                        *failed = true;
                        reply->deleteLater();
                        QMessageBox::critical(this, QStringLiteral("GFYMS Update"), QStringLiteral("Cannot save update: %1").arg(name));
                        return;
                    }
                    package.write(reply->readAll());
                    package.close();
                    reply->deleteLater();

                    const QString expected = expectedHash(sums, name);
                    QFile verify(path);
                    if (!expected.isEmpty() && verify.open(QIODevice::ReadOnly)) {
                        const QString actual = QString::fromLatin1(QCryptographicHash::hash(verify.readAll(), QCryptographicHash::Sha256).toHex());
                        if (expected != actual) {
                            *failed = true;
                            QMessageBox::critical(this, QStringLiteral("GFYMS Update"), QStringLiteral("SHA-256 verification failed for %1.").arg(name));
                            return;
                        }
                    }
                    replyState->push_back(path);
                    downloadNext(index + 1);
                });
            };
            downloadNext(0);
        };

        if (sumsUrl.isEmpty()) {
            continueWithSums(QByteArray());
            return;
        }

        QNetworkRequest sumsRequest{QUrl(sumsUrl)};
        sumsRequest.setHeader(QNetworkRequest::UserAgentHeader, QStringLiteral("GFYMS-Center"));
        auto *sumsReply = network_->get(sumsRequest);
        connect(sumsReply, &QNetworkReply::finished, this, [this, sumsReply, continueWithSums] {
            sumsReply->deleteLater();
            if (sumsReply->error() != QNetworkReply::NoError) {
                QMessageBox::critical(this, QStringLiteral("GFYMS Update"), QStringLiteral("Could not download SHA256SUMS."));
                return;
            }
            continueWithSums(sumsReply->readAll());
        });
    }
    void installPackage(const QString &path)
    {
        const int code = QProcess::execute(QStringLiteral("pkexec"),
            {QStringLiteral("/usr/libexec/gfyms-update-helper"), QStringLiteral("install"), path});
        progress_->setValue(100);
        if (code == 0) {
            QMessageBox::information(this, QStringLiteral("GFYMS Update"),
                                     QStringLiteral("GFYMS was updated. Reboot if kernel integration changed."));
        } else {
            QMessageBox::critical(this, QStringLiteral("GFYMS Update"),
                                  QStringLiteral("GFYMS update helper failed."));
        }
    }

    void rollback()
    {
        const int code = QProcess::execute(QStringLiteral("pkexec"),
            {QStringLiteral("/usr/libexec/gfyms-update-helper"), QStringLiteral("rollback")});
        QMessageBox::information(this, QStringLiteral("GFYMS Rollback"),
            code == 0 ? QStringLiteral("The cached previous GFYMS package was restored.")
                      : QStringLiteral("No cached rollback package was restored."));
    }

    QNetworkAccessManager *network_;
    QTabWidget *tabs_ = nullptr;
    QListWidget *releases_ = nullptr;
    QTextBrowser *notes_ = nullptr;
    QProgressBar *progress_ = nullptr;
    QJsonArray releasesData_;
    QSettings settings_{QStringLiteral("GFYMS"), QStringLiteral("GFYMS Center")};
};

int main(int argc, char **argv)
{
    QApplication app(argc, argv);
    app.setApplicationName(QStringLiteral("GFYMS Center"));
    app.setApplicationDisplayName(QStringLiteral("GFYMS Center"));
    app.setOrganizationName(QStringLiteral("GFYMS"));
    GfymsCenter window;
    window.show();
    return app.exec();
}
