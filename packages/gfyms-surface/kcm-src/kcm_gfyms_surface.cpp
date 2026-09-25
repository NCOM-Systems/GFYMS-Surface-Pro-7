#include <KQuickConfigModule>
#include <KPluginFactory>
#include <QFile>
#include <QSettings>

class GfymsSurfaceConfig final : public KQuickConfigModule
{
    Q_OBJECT

public:
    explicit GfymsSurfaceConfig(QObject *parent, const KPluginMetaData &metaData)
        : KQuickConfigModule(parent, metaData)
    {
    }

    Q_INVOKABLE QString productName() const
    {
        return readFile(QStringLiteral("/sys/class/dmi/id/product_name"), QStringLiteral("Unknown"));
    }

    Q_INVOKABLE QString kernelVersion() const
    {
        return readFile(QStringLiteral("/proc/sys/kernel/osrelease"), QStringLiteral("Unknown"));
    }

    Q_INVOKABLE bool isSurfacePro7() const
    {
        return productName().contains(QStringLiteral("Surface Pro 7"), Qt::CaseInsensitive);
    }

    Q_INVOKABLE int penPressure() const
    {
        return settings().value(QStringLiteral("pen/pressure"), 50).toInt();
    }

    Q_INVOKABLE void setPenPressure(int value)
    {
        settings().setValue(QStringLiteral("pen/pressure"), qBound(0, value, 100));
    }

    Q_INVOKABLE int penHand() const
    {
        return settings().value(QStringLiteral("pen/hand"), 0).toInt();
    }

    Q_INVOKABLE void setPenHand(int value)
    {
        settings().setValue(QStringLiteral("pen/hand"), qBound(0, value, 1));
    }

    Q_INVOKABLE int penTopButton() const
    {
        return settings().value(QStringLiteral("pen/top-button"), 0).toInt();
    }

    Q_INVOKABLE void setPenTopButton(int value)
    {
        settings().setValue(QStringLiteral("pen/top-button"), qBound(0, value, 3));
    }

    Q_INVOKABLE int penSideButton() const
    {
        return settings().value(QStringLiteral("pen/side-button"), 0).toInt();
    }

    Q_INVOKABLE void setPenSideButton(int value)
    {
        settings().setValue(QStringLiteral("pen/side-button"), qBound(0, value, 2));
    }

private:
    static QSettings settings()
    {
        return QSettings(QStringLiteral("GFYMS"), QStringLiteral("Surface"));
    }

    static QString readFile(const QString &path, const QString &fallback)
    {
        QFile file(path);
        if (!file.open(QIODevice::ReadOnly | QIODevice::Text))
            return fallback;
        const QString value = QString::fromUtf8(file.readAll()).trimmed();
        return value.isEmpty() ? fallback : value;
    }
};

K_PLUGIN_CLASS_WITH_JSON(GfymsSurfaceConfig, "kcm_gfyms_surface.json")
#include "kcm_gfyms_surface.moc"
