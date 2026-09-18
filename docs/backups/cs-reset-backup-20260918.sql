
/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

LOCK TABLES `return_orders` WRITE;
/*!40000 ALTER TABLE `return_orders` DISABLE KEYS */;
INSERT INTO `return_orders` (`id`, `return_id`, `order_id`, `user_id`, `items`, `reason`, `refund_amount`, `status`, `session_id`, `created_at`) VALUES (75,'RC-1787889704439',113,2,'[{\"name\": \"手机壳\", \"refund\": 29.9, \"item_id\": \"SKU-001\", \"quantity\": 1}, {\"name\": \"钢化膜\", \"refund\": 39.8, \"item_id\": \"SKU-002\", \"quantity\": 2}]','质量问题',69.70,'APPROVED','847807a1759f45f588abe5f52a22f3f6','2026-08-28 04:01:44');
/*!40000 ALTER TABLE `return_orders` ENABLE KEYS */;
UNLOCK TABLES;

LOCK TABLES `refund_orders` WRITE;
/*!40000 ALTER TABLE `refund_orders` DISABLE KEYS */;
INSERT INTO `refund_orders` (`id`, `refund_id`, `order_id`, `user_id`, `reason`, `amount`, `status`, `session_id`, `created_at`) VALUES (6,'RF-1787533485714',115,2,'不想要了',59.90,'APPROVED','ed815ccd74fd44caa93284cd7ac0aa29','2026-08-24 01:04:45');
/*!40000 ALTER TABLE `refund_orders` ENABLE KEYS */;
UNLOCK TABLES;

LOCK TABLES `complaint_tickets` WRITE;
/*!40000 ALTER TABLE `complaint_tickets` DISABLE KEYS */;
INSERT INTO `complaint_tickets` (`id`, `ticket_id`, `user_id`, `order_id`, `complaint_type`, `description`, `severity`, `status`, `session_id`, `created_at`, `idempotency_key`) VALUES (8,'CT-1787568981620',1,NULL,'商品质量','我买的手机屏幕碎了，明显质量问题','MEDIUM','OPEN','probe-c2','2026-08-24 10:56:21',NULL);
INSERT INTO `complaint_tickets` (`id`, `ticket_id`, `user_id`, `order_id`, `complaint_type`, `description`, `severity`, `status`, `session_id`, `created_at`, `idempotency_key`) VALUES (9,'CT-1787569041165',5,NULL,'商品质量','我买的手机屏幕碎了，明显质量问题','MEDIUM','OPEN','a52b211f8f4547358d1c8ec57df2cb9e','2026-08-24 10:57:21',NULL);
INSERT INTO `complaint_tickets` (`id`, `ticket_id`, `user_id`, `order_id`, `complaint_type`, `description`, `severity`, `status`, `session_id`, `created_at`, `idempotency_key`) VALUES (10,'CT-1787569333630',5,NULL,'商品质量','我买的手机屏幕碎了，明显质量问题','MEDIUM','OPEN','2f2a5727fade45a1a38aa634480f521f','2026-08-24 11:02:13',NULL);
INSERT INTO `complaint_tickets` (`id`, `ticket_id`, `user_id`, `order_id`, `complaint_type`, `description`, `severity`, `status`, `session_id`, `created_at`, `idempotency_key`) VALUES (11,'CT-1787569916289',5,NULL,'商品质量','我买的手机屏幕碎了，明显质量问题','MEDIUM','OPEN','c9200f136e384f10b8a9808530991643','2026-08-24 11:11:56',NULL);
INSERT INTO `complaint_tickets` (`id`, `ticket_id`, `user_id`, `order_id`, `complaint_type`, `description`, `severity`, `status`, `session_id`, `created_at`, `idempotency_key`) VALUES (12,'CT-1787570156334',5,NULL,'商品质量','我买的手机屏幕碎了，明显质量问题','MEDIUM','OPEN','ad9b60d73ce14ab1833c4f1078c827d0','2026-08-24 11:15:56',NULL);
INSERT INTO `complaint_tickets` (`id`, `ticket_id`, `user_id`, `order_id`, `complaint_type`, `description`, `severity`, `status`, `session_id`, `created_at`, `idempotency_key`) VALUES (13,'CT-1787570205529',5,NULL,'商品质量','我买的手机屏幕碎了，明显质量问题','MEDIUM','OPEN','f6db24553b224294af3b62f906d676c3','2026-08-24 11:16:45',NULL);
INSERT INTO `complaint_tickets` (`id`, `ticket_id`, `user_id`, `order_id`, `complaint_type`, `description`, `severity`, `status`, `session_id`, `created_at`, `idempotency_key`) VALUES (14,'CT-1787570221900',5,NULL,'商品质量','我买的手机屏幕碎了，明显质量问题','MEDIUM','OPEN','0f18b9b065684af584e5cf963a9ef398','2026-08-24 11:17:01',NULL);
INSERT INTO `complaint_tickets` (`id`, `ticket_id`, `user_id`, `order_id`, `complaint_type`, `description`, `severity`, `status`, `session_id`, `created_at`, `idempotency_key`) VALUES (15,'CT-1787571100422',5,NULL,'商品质量','我买的手机屏幕碎了，明显质量问题','MEDIUM','OPEN','dc9d580055c949ab989dd34d063b7811','2026-08-24 11:31:40',NULL);
INSERT INTO `complaint_tickets` (`id`, `ticket_id`, `user_id`, `order_id`, `complaint_type`, `description`, `severity`, `status`, `session_id`, `created_at`, `idempotency_key`) VALUES (16,'CT-1787571120324',5,NULL,'商品质量','我买的手机屏幕碎了，明显质量问题','MEDIUM','OPEN','38a7015edc1147009cdb6f6d3455795f','2026-08-24 11:32:00',NULL);
INSERT INTO `complaint_tickets` (`id`, `ticket_id`, `user_id`, `order_id`, `complaint_type`, `description`, `severity`, `status`, `session_id`, `created_at`, `idempotency_key`) VALUES (17,'CT-1787572128773',5,NULL,'商品质量','我买的手机屏幕碎了，明显质量问题','MEDIUM','OPEN','8ac3152749e24c4e9d9913200751929d','2026-08-24 11:48:48',NULL);
INSERT INTO `complaint_tickets` (`id`, `ticket_id`, `user_id`, `order_id`, `complaint_type`, `description`, `severity`, `status`, `session_id`, `created_at`, `idempotency_key`) VALUES (18,'CT-1787572144405',5,NULL,'商品质量','我买的手机屏幕碎了，明显质量问题','MEDIUM','OPEN','103bd9ed434b4c229827907a0a62f9f5','2026-08-24 11:49:04',NULL);
INSERT INTO `complaint_tickets` (`id`, `ticket_id`, `user_id`, `order_id`, `complaint_type`, `description`, `severity`, `status`, `session_id`, `created_at`, `idempotency_key`) VALUES (19,'CT-1787572441483',5,NULL,'商品质量','我买的手机屏幕碎了，明显质量问题','MEDIUM','OPEN','ed22fd8051cf4b638cf937ca098529f2','2026-08-24 11:54:01',NULL);
INSERT INTO `complaint_tickets` (`id`, `ticket_id`, `user_id`, `order_id`, `complaint_type`, `description`, `severity`, `status`, `session_id`, `created_at`, `idempotency_key`) VALUES (20,'CT-1787573072794',5,NULL,'商品质量','我买的手机屏幕碎了，明显质量问题','MEDIUM','OPEN','b151c93c08cb4821876ce849af4972a2','2026-08-24 12:04:32',NULL);
INSERT INTO `complaint_tickets` (`id`, `ticket_id`, `user_id`, `order_id`, `complaint_type`, `description`, `severity`, `status`, `session_id`, `created_at`, `idempotency_key`) VALUES (21,'CT-1787721241168',5,NULL,'商品质量','我买的手机屏幕碎了，明显质量问题','MEDIUM','OPEN','6cc8357047f94ccead5ec8cc9fd59c45','2026-08-26 05:14:01','CT:f239219b350fdb222dec1a9994edec4f');
INSERT INTO `complaint_tickets` (`id`, `ticket_id`, `user_id`, `order_id`, `complaint_type`, `description`, `severity`, `status`, `session_id`, `created_at`, `idempotency_key`) VALUES (26,'CT-1787725765473',5,NULL,'商品质量','我买的手机屏幕碎了，明显是质量问题','MEDIUM','OPEN','unit-complaint','2026-08-26 06:29:25','CT:9408764584ea1fcf5905b7e653b29938');
INSERT INTO `complaint_tickets` (`id`, `ticket_id`, `user_id`, `order_id`, `complaint_type`, `description`, `severity`, `status`, `session_id`, `created_at`, `idempotency_key`) VALUES (29,'CT-1787890019382',2,NULL,'物流问题','快递员送货上门时态度很差，还推搡我','MEDIUM','OPEN','add67b40459e4e8ba7d0d348ad9c6c0e','2026-08-28 04:06:59','CT:40f0a443b93db09acb9ae2cfc620c5e7');
/*!40000 ALTER TABLE `complaint_tickets` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

