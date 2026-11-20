// U9311/F FMVU34013, BIOS 2.47. Paths and STAS field from its DSDT.
DefinitionBlock ("", "SSDT", 2, "U9311", "U9311CFG", 1)
{
    External (\STAS, FieldUnitObj)
    External (\_SB.PR00, ProcessorObj)
    External (\_SB.PC00.GFX0, DeviceObj)

    // Only the DSDT's single Windows 2015 query is redirected here.
    // The firmware then supplies the I2C bus resource to EPTP._CRS.
    Method (XOSI, 1, NotSerialized)
    {
        If (_OSI ("Darwin")) { Return (One) }
        Return (_OSI (Arg0))
    }

    Scope (\)
    {
        Method (_INI, 0, NotSerialized)
        {
            If (_OSI ("Darwin")) { STAS = One }
        }
    }
    Scope (\_SB.PR00)
    {
        Method (_DSM, 4, NotSerialized)
        {
            If (Arg2 == Zero) { Return (Buffer () { 0x03 }) }
            Return (Package () { "plugin-type", One })
        }
    }
    Scope (\_SB.PC00.GFX0)
    {
        Device (PNLF)
        {
            Name (_HID, EisaId ("APP0002"))
            Name (_CID, "backlight")
            Name (_UID, 19)
            Method (_STA, 0, NotSerialized)
            {
                If (_OSI ("Darwin")) { Return (0x0B) }
                Return (Zero)
            }
        }
    }
    Scope (\_SB)
    {
        Device (USBX)
        {
            Name (_ADR, Zero)
            Method (_STA, 0, NotSerialized)
            {
                If (_OSI ("Darwin")) { Return (0x0F) }
                Return (Zero)
            }
            Method (_DSM, 4, NotSerialized)
            {
                If (Arg2 == Zero) { Return (Buffer () { 0x03 }) }
                Return (Package ()
                {
                    "kUSBSleepPowerSupply", 0x13EC,
                    "kUSBSleepPortCurrentLimit", 0x0834,
                    "kUSBWakePowerSupply", 0x13EC,
                    "kUSBWakePortCurrentLimit", 0x0834
                })
            }
        }
    }
}
