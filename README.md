# Wynn's Toolkits

เครื่องมือทำงานสำหรับเพื่อนๆใน Blender ออกแบบมาเพื่อ Project Bifrost.

## รายละเอียด

### 🎬 เครื่องมือแอนิเมชัน
อยู่ในแท็บ **Animation** ในแถบด้านข้าง *Wynn's Toolkits*

*   **Silhouette Tool :** เปลี่ยนมุมมองเป็นโหมดเงาดำเพื่อตรวจสอบท่าทางและเส้นการเคลื่อนไหว
    *   กำหนดสีเงาดำและสีพื้นหลังได้เอง
    *   ตัวเลือกซ่อน Overlay อัตโนมัติ
*   **Motion Path Tools:** ควบคุมการคำนวณ อัปเดต และลบเส้นทางการเคลื่อนไหวของวัตถุหรือกระดูกที่เลือก
*   **Playblast Tool:** เรนเดอร์ mp4 ลงไดร์ฟ Google พร้อม metadata burn in (ศิลปิน, ชื่อฉาก, วันที่, เวลา, เฟรม, ฯลฯ)
    *   ตั้งชื่อไฟล์อัตโนมัติตามชื่อ Scene
    *   บังคับโหมดสี Texture และ Wireframe แบบ Theme ขณะเรนเดอร์
*   **Pie menu (`Shift + V`):** เปิดเครื่องมือ Silhouette และ Motion Path ได้ด้วย shortcut

### 🦴 เครื่องมือ Rigging
อยู่ในแท็บ **Rig** ในแถบด้านข้าง *Wynn's Toolkits*

*   **Parent Binary Weights:** เชื่อม Mesh กับ Armature แบบ Weight Binary (น้ำหนัก 0 กับ 1 เท่านั้น) โดยคำนวณจากกระดูกที่ใกล้ที่สุด *Algorithm ยังใหม่อยู่จะอัเดทในอนาคตให้  Assign Bone เดี่ยวได้ดีกว่านี้
*   **Deform Bones:** โหมดช่วย Weight Paint โดยจะ Solo เฉพาะ Bone Collection ที่มีคำว่า 'Deform'
*   **Setup Weight Paint:** สลับโหมด Weight Paint/Object Mode พร้อมตั้งค่า Viewport พร้อมปรับ Brush Constant (Show Wire, In Front) อัตโนมัติ
*   **Smooth Symmetrize:** Smooth กระดูกที่เลือกทั้งซ้ายเเละขวาในอนาคตจะปรับให้ปรับได้มากกว่านี้
*   **Pie menu (`V`):** คีย์ลัดสำหรับเรียกใช้เครื่องมือ Rigging

### 🧊 เครื่องมือโมเดลลิ่ง
อยู่ในแท็บ **Model** ในแถบด้านข้าง *Wynn's Toolkits*

*   **Vertex ID:** เลือกเเละเพิ่มสี Vertex color ใน Edit mode.
    *   **Preset colors:** แดง, เขียว, น้ำเงิน, เหลือง, ฟ้าอมเขียว
    *   **Assign:** เพิ่มสีที่เลือกเข้าไปใน face,vertex,edge ที่เลือก
    *   **Select:** เลือก face,vertex,edge ที่ตรงกับสี
    *   **Remove Color Attribute:** ลบ Vertex color ทั้งหมด

## วิธีการติดตั้ง

1.  ดาวน์โหลด `Wynn's Toolkits`
2.  บีบอัดเป็นไฟล์ zip และติดตั้งผ่าน `Edit > Preferences > Add-ons > Install...` หรือ ลาก zip เข้าหน้าต่าง Blender
3.  เปิดใช้งาน addon โดยติ๊กที่ **Wynn's Toolkits**

## วิธีการใช้งาน

*   **แถบด้านข้าง:** กด `N` ใน 3D Viewport และไปที่แท็บ **Wynn's Toolkits**
*   **เมนูพายแอนิเมชัน:** กด `Shift + V` ใน 3D Viewport
*   **เมนูพาย Rigging:** กด `V` ใน 3D Viewport

## ข้อกำหนด
*   Blender 5.0 ++ ได้โปรด

---
**ผู้พัฒนา:** suthiphan khamnong
**เวอร์ชัน:** 1.2